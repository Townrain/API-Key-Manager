use std::fs;
use std::os::windows::process::CommandExt;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::{Manager, State};

// --- Windows Job Object: ensure child processes die with parent ---

mod job {
    use std::os::windows::io::AsRawHandle;

    #[repr(C)]
    struct IoCounters {
        _read: u64,
        _read_op: u64,
        _write: u64,
        _write_op: u64,
        _other: u64,
        _other_op: u64,
    }

    #[repr(C)]
    struct JobObjectExtendedLimitInformation {
        basic_limit: BasicLimitInformation,
        _io_info: IoCounters,
        _process_memory_limit: usize,
        _job_memory_limit: usize,
        _peak_process_memory: usize,
        _peak_job_memory: usize,
    }

    #[repr(C)]
    struct BasicLimitInformation {
        _per_process_user_time_limit: i64,
        _per_job_user_time_limit: i64,
        limit_flags: u32,
        _minimum_working_set_size: usize,
        _maximum_working_set_size: usize,
        _active_process_limit: u32,
        _affinity: usize,
        _priority: u32,
        _scheduling_class: u32,
    }

    const JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: u32 = 0x2000;
    const JOB_OBJECT_EXTENDED_LIMIT_INFORMATION: u32 = 9;

    extern "system" {
        fn CreateJobObjectW(lp_job_attributes: *const std::ffi::c_void, lp_name: *const u16) -> isize;
        fn SetInformationJobObject(
            h_job: isize,
            info_class: u32,
            lp_job_object_info: *const JobObjectExtendedLimitInformation,
            cb_job_object_info_length: u32,
        ) -> i32;
        fn AssignProcessToJobObject(h_job: isize, h_process: isize) -> i32;
    }

    /// Create a Job Object with KILL_ON_JOB_CLOSE and assign the child process to it.
    /// When the parent (this exe) exits for any reason, the OS automatically terminates
    /// all processes in the job.
    pub fn assign_child_to_job(child: &std::process::Child) {
        unsafe {
            let job = CreateJobObjectW(std::ptr::null(), std::ptr::null());
            if job == 0 {
                log::warn!("CreateJobObjectW failed, child process may survive parent crash");
                return;
            }

            let info = JobObjectExtendedLimitInformation {
                basic_limit: BasicLimitInformation {
                    _per_process_user_time_limit: 0,
                    _per_job_user_time_limit: 0,
                    limit_flags: JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
                    _minimum_working_set_size: 0,
                    _maximum_working_set_size: 0,
                    _active_process_limit: 0,
                    _affinity: 0,
                    _priority: 0,
                    _scheduling_class: 0,
                },
                _io_info: IoCounters { _read: 0, _read_op: 0, _write: 0, _write_op: 0, _other: 0, _other_op: 0 },
                _process_memory_limit: 0,
                _job_memory_limit: 0,
                _peak_process_memory: 0,
                _peak_job_memory: 0,
            };

            let ret = SetInformationJobObject(
                job,
                JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                &info,
                std::mem::size_of::<JobObjectExtendedLimitInformation>() as u32,
            );
            if ret == 0 {
                log::warn!("SetInformationJobObject failed");
                return;
            }

            let handle = child.as_raw_handle() as isize;
            let ret = AssignProcessToJobObject(job, handle);
            if ret == 0 {
                log::warn!("AssignProcessToJobObject failed (process may already be dead)");
            } else {
                log::info!("Child PID {} assigned to Job Object", child.id());
            }
            // Leak the job handle intentionally — it stays alive for the process lifetime.
            // When the process exits (any reason), the OS closes the handle and kills all
            // assigned child processes via JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE.
        }
    }
}

// --- Backend process management ---

struct BackendProcess(Mutex<Option<Child>>);

#[tauri::command]
fn read_file_text(path: String) -> Result<String, String> {
    fs::read_to_string(&path).map_err(|e| format!("Failed to read {}: {}", path, e))
}

fn find_backend_exe(exe_dir: &std::path::Path) -> Option<std::path::PathBuf> {
    let bundled = exe_dir.join("keyhub-backend.exe");
    if bundled.exists() {
        return Some(bundled);
    }
    None
}

fn find_backend_dir(exe_dir: &std::path::Path) -> Option<std::path::PathBuf> {
    // Walk up from exe location to find a directory containing web.py
    let mut dir = exe_dir.to_path_buf();
    for _ in 0..8 {
        if dir.join("web.py").exists() {
            return Some(dir);
        }
        let sub = dir.join("API-Key-Manager-4.3.0");
        if sub.join("web.py").exists() {
            return Some(sub);
        }
        if !dir.pop() {
            break;
        }
    }
    None
}

fn spawn_backend(backend: &State<BackendProcess>) {
    // Don't spawn if already running
    if let Ok(guard) = backend.0.lock() {
        if guard.is_some() {
            return;
        }
    }

    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|p| p.to_path_buf()))
        .unwrap_or_default();

    // Try bundled backend exe first
    if let Some(backend_exe) = find_backend_exe(&exe_dir) {
        log::info!("Starting bundled backend from {:?}", backend_exe);
        match Command::new(&backend_exe)
            .arg("--port")
            .arg("18001")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .stdin(Stdio::null())
            .creation_flags(0x08000000) // CREATE_NO_WINDOW
            .spawn()
        {
            Ok(child) => {
                log::info!("Backend started, PID: {}", child.id());
                job::assign_child_to_job(&child);
                if let Ok(mut guard) = backend.0.lock() {
                    *guard = Some(child);
                }
            }
            Err(e) => {
                log::error!("Failed to start bundled backend: {}", e);
            }
        }
        return;
    }

    // Fall back to Python-based backend
    let backend_dir = match find_backend_dir(&exe_dir) {
        Some(dir) => dir,
        None => {
            log::error!("Cannot find backend from {:?}", exe_dir);
            return;
        }
    };

    log::info!("Starting Python backend from {:?}", backend_dir);

    match Command::new("python")
        .arg("web.py")
        .arg("--desktop")
        .arg("--port")
        .arg("18001")
        .current_dir(&backend_dir)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .stdin(Stdio::null())
        .creation_flags(0x08000000) // CREATE_NO_WINDOW
        .spawn()
    {
        Ok(child) => {
            log::info!("Backend started, PID: {}", child.id());
            job::assign_child_to_job(&child);
            if let Ok(mut guard) = backend.0.lock() {
                *guard = Some(child);
            }
        }
        Err(e) => {
            log::error!("Failed to start backend: {}", e);
        }
    }
}

fn kill_backend(backend: &State<BackendProcess>) {
    if let Ok(mut guard) = backend.0.lock() {
        if let Some(mut child) = guard.take() {
            log::info!("Killing backend, PID: {}", child.id());
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(BackendProcess(Mutex::new(None)))
        .plugin(
            tauri_plugin_log::Builder::default()
                .level(log::LevelFilter::Info)
                .build(),
        )
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![read_file_text])
        .setup(|app| {
            let backend = app.state::<BackendProcess>();
            spawn_backend(&backend);
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let backend = window.state::<BackendProcess>();
                kill_backend(&backend);
                log::info!("Exiting process");
                std::process::exit(0);
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
