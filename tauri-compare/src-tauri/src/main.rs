// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
  // Kill any OTHER existing app.exe instances before starting
  #[cfg(target_os = "windows")]
  {
    let current_pid = std::process::id();
    // Use PowerShell to kill app.exe processes with a different PID
    let script = format!(
      "Get-Process -Name app -ErrorAction SilentlyContinue | Where-Object {{ $_.Id -ne {} }} | Stop-Process -Force",
      current_pid
    );
    let _ = std::process::Command::new("powershell")
      .args(["-NoProfile", "-Command", &script])
      .stdout(std::process::Stdio::null())
      .stderr(std::process::Stdio::null())
      .status();
    std::thread::sleep(std::time::Duration::from_millis(300));
  }

  app_lib::run();
}
