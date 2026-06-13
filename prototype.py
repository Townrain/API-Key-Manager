#!/usr/bin/env python3
"""
C++ 耦合性检测工具 — 原型实现
Creative Disruptor 的 6 种非常规检测方法的可执行原型

使用方法:
    python prototype.py /path/to/cpp/project
    
依赖:
    pip install networkx
"""

import os
import re
import sys
import subprocess
import tempfile
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    print("Warning: networkx not installed. Graph analysis limited.")


# ============================================================
# Data Structures
# ============================================================

@dataclass
class IncludeEdge:
    """include dependency edge"""
    source: str      # includer (TU or header)
    target: str      # included (header)
    is_direct: bool  # direct include
    condition: str = ""  # conditional compilation condition

@dataclass
class TUDependency:
    """translation unit dependency"""
    tu: str
    headers: List[str] = field(default_factory=list)
    
@dataclass
class BRIResult:
    """Blast Radius Index result"""
    header: str
    bri: float
    dependent_tus: Set[str] = field(default_factory=set)
    total_tus: int = 0

@dataclass
class SelfContainmentResult:
    """self-containment test result"""
    header: str
    is_self_contained: bool
    missing_headers: List[str] = field(default_factory=list)
    error_message: str = ""

@dataclass
class CycleResult:
    """circular dependency result"""
    cycle: List[str]
    severity: str
    symbol_deps: List[str] = field(default_factory=list)
    break_suggestion: str = ""


# ============================================================
# Method 1: Self-Containment Blaster
# ============================================================

class SelfContainmentBlaster:
    """
    Test if each header file can be compiled independently.
    Can compile independently = no external implicit dependencies.
    """
    
    def __init__(self, compiler: str = "clang++", std: str = "c++17"):
        self.compiler = compiler
        self.std = std
    
    def blast(self, header_path: str, include_dirs: List[str] = None) -> SelfContainmentResult:
        """Test single header self-containment"""
        if include_dirs is None:
            include_dirs = []
        
        # Generate temp file
        with tempfile.NamedTemporaryFile(
            suffix='.cpp', mode='w', delete=False, encoding='utf-8'
        ) as f:
            f.write(f'#include "{header_path}"\n')
            f.write('int main() { return 0; }\n')
            temp_cpp = f.name
        
        try:
            # Build compile command
            cmd = [
                self.compiler,
                '-fsyntax-only',
                f'-std={self.std}',
            ]
            
            # Add include directories
            for d in include_dirs:
                cmd.extend(['-I', d])
            
            cmd.append(temp_cpp)
            
            # Compile
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return SelfContainmentResult(
                    header=header_path,
                    is_self_contained=True
                )
            else:
                # Extract undeclared identifiers
                missing = self._parse_undeclared_identifiers(result.stderr)
                return SelfContainmentResult(
                    header=header_path,
                    is_self_contained=False,
                    missing_headers=missing,
                    error_message=result.stderr[:500]
                )
        except subprocess.TimeoutExpired:
            return SelfContainmentResult(
                header=header_path,
                is_self_contained=False,
                error_message="Compile timeout"
            )
        except FileNotFoundError:
            return SelfContainmentResult(
                header=header_path,
                is_self_contained=False,
                error_message=f"Compiler {self.compiler} not found"
            )
        finally:
            os.unlink(temp_cpp)
    
    def blast_all(self, headers: List[str], include_dirs: List[str] = None) -> List[SelfContainmentResult]:
        """Batch test all headers"""
        results = []
        for header in headers:
            result = self.blast(header, include_dirs)
            results.append(result)
        return results
    
    def compute_ratio(self, results: List[SelfContainmentResult]) -> float:
        """Calculate self-containment ratio"""
        if not results:
            return 0.0
        contained = sum(1 for r in results if r.is_self_contained)
        return contained / len(results)
    
    def _parse_undeclared_identifiers(self, stderr: str) -> List[str]:
        """Extract undeclared identifiers from compile errors"""
        undeclared = []
        for line in stderr.split('\n'):
            match = re.search(r"use of undeclared identifier '(\w+)'", line)
            if match:
                undeclared.append(match.group(1))
        return undeclared


# ============================================================
# Method 2: Include Graph Analysis + BRI
# ============================================================

class IncludeGraphAnalyzer:
    """
    Parse #include relationships, build dependency graph, calculate BRI.
    """
    
    def __init__(self):
        self.graph: Dict[str, Set[str]] = defaultdict(set)  # header -> headers it includes
        self.reverse_graph: Dict[str, Set[str]] = defaultdict(set)  # header -> headers that include it
        self.tu_headers: Dict[str, List[str]] = {}  # TU -> its includes
    
    def parse_file(self, file_path: str) -> List[str]:
        """Parse file's #include list"""
        includes = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    # Match #include "..." or #include <...>
                    match = re.match(r'#\s*include\s+[<"]([^>"]+)[>"]', line)
                    if match:
                        includes.append(match.group(1))
        except Exception as e:
            print(f"Warning: Cannot parse {file_path}: {e}")
        return includes
    
    def scan_directory(self, directory: str, extensions: List[str] = None):
        """Scan directory, build dependency graph"""
        if extensions is None:
            extensions = ['.h', '.hpp', '.hxx', '.cpp', '.cc', '.cxx']
        
        for root, dirs, files in os.walk(directory):
            for file in files:
                if any(file.endswith(ext) for ext in extensions):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, directory)
                    
                    includes = self.parse_file(file_path)
                    self.tu_headers[rel_path] = includes
                    
                    # Build graph
                    for inc in includes:
                        self.graph[rel_path].add(inc)
                        self.reverse_graph[inc].add(rel_path)
    
    def compute_bri(self, header: str, total_tus: int) -> BRIResult:
        """Calculate single header's BRI"""
        if total_tus == 0:
            return BRIResult(header=header, bri=0.0, total_tus=0)
        
        # Find all TUs that directly or indirectly depend on this header
        dependent_tus = set()
        
        # BFS on reverse graph
        queue = [header]
        visited = {header}
        
        while queue:
            current = queue.pop(0)
            for tu in self.reverse_graph.get(current, set()):
                if tu not in visited:
                    visited.add(tu)
                    if self._is_tu(tu):
                        dependent_tus.add(tu)
                    else:
                        queue.append(tu)
        
        bri = len(dependent_tus) / total_tus
        
        return BRIResult(
            header=header,
            bri=bri,
            dependent_tus=dependent_tus,
            total_tus=total_tus
        )
    
    def compute_all_bri(self) -> List[BRIResult]:
        """Calculate all headers' BRI"""
        total_tus = sum(1 for tu in self.tu_headers if self._is_tu(tu))
        
        headers = set()
        for includes in self.tu_headers.values():
            for inc in includes:
                headers.add(inc)
        
        results = []
        for header in headers:
            result = self.compute_bri(header, total_tus)
            results.append(result)
        
        return sorted(results, key=lambda r: r.bri, reverse=True)
    
    def _is_tu(self, path: str) -> bool:
        """Check if path is a translation unit (.cpp file)"""
        return path.endswith(('.cpp', '.cc', '.cxx'))


# ============================================================
# Method 3: Cycle Detection
# ============================================================

class CycleDetector:
    """
    Detect circular dependencies using Tarjan's algorithm for SCCs.
    """
    
    def __init__(self, graph: Dict[str, Set[str]]):
        self.graph = graph
        self.index = 0
        self.stack = []
        self.indices = {}
        self.lowlinks = {}
        self.on_stack = set()
        self.sccs = []
    
    def find_cycles(self) -> List[List[str]]:
        """Find all strongly connected components (circular dependencies)"""
        for node in self.graph:
            if node not in self.indices:
                self._strongconnect(node)
        
        # Filter: only keep SCCs with size >= 2 (self-loops don't count)
        return [scc for scc in self.sccs if len(scc) >= 2]
    
    def _strongconnect(self, v):
        self.indices[v] = self.index
        self.lowlinks[v] = self.index
        self.index += 1
        self.stack.append(v)
        self.on_stack.add(v)
        
        for w in self.graph.get(v, set()):
            if w not in self.indices:
                self._strongconnect(w)
                self.lowlinks[v] = min(self.lowlinks[v], self.lowlinks[w])
            elif w in self.on_stack:
                self.lowlinks[v] = min(self.lowlinks[v], self.indices[w])
        
        if self.lowlinks[v] == self.indices[v]:
            scc = []
            while True:
                w = self.stack.pop()
                self.on_stack.remove(w)
                scc.append(w)
                if w == v:
                    break
            self.sccs.append(scc)
    
    def evaluate_severity(self, cycle: List[str]) -> str:
        """Evaluate cycle severity"""
        size = len(cycle)
        if size > 10:
            return "CRITICAL"
        elif size > 5:
            return "HIGH"
        elif size > 3:
            return "MEDIUM"
        else:
            return "LOW"
    
    def suggest_break_point(self, cycle: List[str]) -> str:
        """Suggest where to break the cycle"""
        if len(cycle) < 2:
            return "No break needed"
        
        # Find node with highest outdegree within cycle
        max_outdegree = -1
        best_node = cycle[0]
        
        for node in cycle:
            outdegree = len(self.graph.get(node, set()) & set(cycle))
            if outdegree > max_outdegree:
                max_outdegree = outdegree
                best_node = node
        
        return f"Break {best_node}'s outgoing edges (highest outdegree: {max_outdegree})"


# ============================================================
# Method 4: Forward Declaration Audit
# ============================================================

class ForwardDeclAuditor:
    """
    Audit forward declaration usage.
    """
    
    def __init__(self):
        self.forward_decls: Dict[str, List[str]] = {}  # file -> forward declarations
        self.includes: Dict[str, List[str]] = {}  # file -> includes
    
    def analyze_file(self, file_path: str) -> Dict:
        """Analyze single file's forward declaration usage"""
        forward_decls = []
        includes = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    
                    # Detect forward declarations
                    match = re.match(r'class\s+(\w+)\s*;', line)
                    if match:
                        forward_decls.append(match.group(1))
                    
                    match = re.match(r'struct\s+(\w+)\s*;', line)
                    if match:
                        forward_decls.append(match.group(1))
                    
                    # Detect includes
                    match = re.match(r'#\s*include\s+[<"]([^>"]+)[>"]', line)
                    if match:
                        includes.append(match.group(1))
        except Exception:
            pass
        
        self.forward_decls[file_path] = forward_decls
        self.includes[file_path] = includes
        
        return {
            'forward_decls': forward_decls,
            'includes': includes,
            'fwd_decl_ratio': len(forward_decls) / max(len(forward_decls) + len(includes), 1)
        }
    
    def compute_coverage(self, files: List[str]) -> float:
        """Calculate forward declaration coverage"""
        total_fwd_decls = 0
        total_potential = 0
        
        for f in files:
            result = self.analyze_file(f)
            total_fwd_decls += len(result['forward_decls'])
            # Rough estimate: each include might be replaceable with forward decl
            total_potential += len(result['includes'])
        
        if total_potential == 0:
            return 1.0
        
        return total_fwd_decls / total_potential


# ============================================================
# Method 5: Macro Propagation Tracer (simplified)
# ============================================================

class MacroTracer:
    """
    Trace macro definitions and usages.
    """
    
    def __init__(self):
        self.macro_defs: Dict[str, str] = {}  # macro_name -> definition_file
        self.macro_uses: Dict[str, List[str]] = defaultdict(list)  # macro_name -> [usage_files]
    
    def scan_file(self, file_path: str):
        """Scan file for macro definitions and usages"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    
                    # Detect #define
                    match = re.match(r'#\s*define\s+(\w+)', line)
                    if match:
                        macro_name = match.group(1)
                        self.macro_defs[macro_name] = file_path
                    
                    # Detect macro usage (simplified: detect uppercase macro names)
                    for macro_name in self.macro_defs:
                        if macro_name in line and not line.strip().startswith('#'):
                            self.macro_uses[macro_name].append(file_path)
        except Exception:
            pass
    
    def find_propagation_hubs(self) -> List[Tuple[str, int]]:
        """Find macro propagation hubs"""
        hub_scores = defaultdict(int)
        
        for macro_name, usage_files in self.macro_uses.items():
            if macro_name in self.macro_defs:
                definition_file = self.macro_defs[macro_name]
                # Propagation score = number of files using this macro
                hub_scores[definition_file] += len(usage_files)
        
        return sorted(hub_scores.items(), key=lambda x: x[1], reverse=True)


# ============================================================
# Method 6: Coupling Budget Enforcer
# ============================================================

class CouplingBudgetEnforcer:
    """
    Coupling budget checker.
    """
    
    def __init__(self, budget: Dict[str, float] = None):
        if budget is None:
            budget = {
                'max_bri': 0.3,           # Maximum BRI threshold
                'max_cycles': 5,           # Maximum circular dependencies
                'min_self_containment': 0.8  # Minimum self-containment ratio
            }
        self.budget = budget
    
    def check(self, bri_results: List[BRIResult], 
              cycles: List[List[str]], 
              self_containment_ratio: float) -> Dict:
        """Check if budget is exceeded"""
        violations = []
        
        # Check BRI
        max_bri = max((r.bri for r in bri_results), default=0)
        if max_bri > self.budget['max_bri']:
            violations.append({
                'metric': 'BRI',
                'current': max_bri,
                'limit': self.budget['max_bri'],
                'severity': 'HIGH' if max_bri > self.budget['max_bri'] * 1.5 else 'MEDIUM'
            })
        
        # Check circular dependencies
        if len(cycles) > self.budget['max_cycles']:
            violations.append({
                'metric': 'CYCLES',
                'current': len(cycles),
                'limit': self.budget['max_cycles'],
                'severity': 'HIGH'
            })
        
        # Check self-containment
        if self_containment_ratio < self.budget['min_self_containment']:
            violations.append({
                'metric': 'SELF_CONTAINMENT',
                'current': self_containment_ratio,
                'limit': self.budget['min_self_containment'],
                'severity': 'HIGH'
            })
        
        return {
            'passed': len(violations) == 0,
            'violations': violations,
            'budget': self.budget
        }


# ============================================================
# Main
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python prototype.py /path/to/cpp/project")
        sys.exit(1)
    
    project_dir = sys.argv[1]
    
    if not os.path.isdir(project_dir):
        print(f"Error: {project_dir} is not a valid directory")
        sys.exit(1)
    
    print(f"{'=' * 60}")
    print(f"C++ Coupling Detection Tool - Prototype")
    print(f"Project: {project_dir}")
    print(f"{'=' * 60}")
    
    # Method 2: Include Graph Analysis + BRI
    print(f"\n{'=' * 60}")
    print("Method 2: Include Graph Analysis + BRI Calculation")
    print("=" * 60)
    
    analyzer = IncludeGraphAnalyzer()
    analyzer.scan_directory(project_dir)
    
    bri_results = analyzer.compute_all_bri()
    
    print(f"\nScanned {len(analyzer.tu_headers)} files")
    print(f"\nTop 10 High BRI Headers:")
    print("-" * 60)
    for i, result in enumerate(bri_results[:10], 1):
        print(f"{i:2d}. {result.header}")
        print(f"    BRI = {result.bri:.1%} ({len(result.dependent_tus)}/{result.total_tus} TU)")
    
    # Method 3: Cycle Detection
    print(f"\n{'=' * 60}")
    print("Method 3: Circular Dependency Detection")
    print("=" * 60)
    
    detector = CycleDetector(analyzer.graph)
    cycles = detector.find_cycles()
    
    if cycles:
        print(f"\nFound {len(cycles)} circular dependencies:")
        print("-" * 60)
        for i, cycle in enumerate(cycles[:10], 1):
            severity = detector.evaluate_severity(cycle)
            suggestion = detector.suggest_break_point(cycle)
            print(f"{i}. Cycle ({severity}): {' -> '.join(cycle)} -> {cycle[0]}")
            print(f"   Suggestion: {suggestion}")
    else:
        print("\nNo circular dependencies found")
    
    # Method 1: Self-Containment Blaster (optional, needs compiler)
    print(f"\n{'=' * 60}")
    print("Method 1: Self-Containment Blaster")
    print("=" * 60)
    
    headers = [h for h in analyzer.graph.keys() if not h.endswith(('.cpp', '.cc', '.cxx'))]
    
    if headers:
        blaster = SelfContainmentBlaster()
        results = blaster.blast_all(headers[:10])  # Only test first 10
        
        non_self_contained = [r for r in results if not r.is_self_contained]
        ratio = blaster.compute_ratio(results)
        
        print(f"\nTested {len(results)} headers")
        print(f"Self-containment ratio: {ratio:.1%}")
        
        if non_self_contained:
            print(f"\nNon-self-contained headers:")
            print("-" * 60)
            for r in non_self_contained:
                print(f"  {r.header}")
                if r.missing_headers:
                    print(f"    Missing: {', '.join(r.missing_headers[:5])}")
    else:
        print("\nNo headers found, skipping test")
    
    # Method 4: Forward Declaration Audit
    print(f"\n{'=' * 60}")
    print("Method 4: Forward Declaration Coverage Audit")
    print("=" * 60)
    
    auditor = ForwardDeclAuditor()
    coverage = auditor.compute_coverage(list(analyzer.tu_headers.keys())[:20])
    print(f"\nForward declaration coverage: {coverage:.1%}")
    
    # Method 6: Coupling Budget Check
    print(f"\n{'=' * 60}")
    print("Method 6: Coupling Budget Check")
    print("=" * 60)
    
    enforcer = CouplingBudgetEnforcer()
    budget_result = enforcer.check(
        bri_results,
        cycles,
        ratio if headers else 1.0
    )
    
    if budget_result['passed']:
        print("\n[PASS] All metrics within budget")
    else:
        print(f"\n[FAIL] Found {len(budget_result['violations'])} violations:")
        print("-" * 60)
        for v in budget_result['violations']:
            print(f"  {v['metric']}: {v['current']:.3f} > {v['limit']:.3f} ({v['severity']})")
    
    print(f"\n{'=' * 60}")
    print("Analysis complete")
    print("=" * 60)


if __name__ == '__main__':
    main()
