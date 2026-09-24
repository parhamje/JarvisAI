"""
actions/safety_guard.py
Human-in-the-Loop Safety Guardrails for JARVIS.

Protects against accidental execution of destructive commands, system file deletions,
disk formatting, or termination of critical operating system services.
"""

import re
from typing import Tuple, Dict, Any

# High-risk patterns in shell commands or script execution
DANGEROUS_PATTERNS = [
    (r"\b(rmdir|rd)\s+.*\/s", "Recursive folder deletion"),
    (r"\bdel\s+.*(\/f|\/q|\/s)", "Forced/silent file deletion"),
    (r"\brm\s+-(r|rf|fr)\b", "Recursive Unix-style deletion"),
    (r"\bformat\s+[a-zA-Z]:", "Disk formatting command"),
    (r"\b(diskpart|fdisk)\b", "Disk partition utility"),
    (r"\bshutdown\s+(\/s|\/r|-s|-r)", "Immediate system shutdown/restart"),
    (r"\btaskkill\s+.*(csrss|smss|svchost|lsass|wininit)", "Terminating critical OS system process"),
    (r"\b(DROP\s+DATABASE|DROP\s+TABLE)\b", "Destructive SQL operation"),
    (r"shutil\.rmtree\(", "Python recursive directory tree removal"),
    (r"os\.remove\(.*[A-Za-z]:[\\\/]Windows", "Deleting files from Windows system directory"),
]


class SafetyGuard:
    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode

    def check_safety(self, tool_name: str, args: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Evaluates whether an action is potentially hazardous.
        Returns: (is_safe: bool, warning_reason: str)
        """
        if not self.strict_mode:
            return True, ""

        # Check Python Script execution
        if tool_name == "run_python_script":
            code = args.get("code") or args.get("script") or ""
            for pat, desc in DANGEROUS_PATTERNS:
                if re.search(pat, code, re.IGNORECASE):
                    return False, f"Potentially destructive code detected: {desc}."

        # Check Autonomous Computer tasks
        if tool_name == "autonomous_computer":
            task = args.get("task", "").lower()
            dangerous_keywords = [
                ("delete system32", "Modifying or deleting Windows system files"),
                ("format drive", "Disk formatting"),
                ("delete everything", "Mass deletion"),
                ("wipe hard drive", "Drive wiping"),
            ]
            for kw, desc in dangerous_keywords:
                if kw in task:
                    return False, f"Autonomous action blocked: {desc}."

        # Check Computer Control / Settings
        if tool_name in ("computer_control", "computer_settings"):
            action = str(args.get("action", "")).lower()
            cmd = str(args.get("command", "")).lower()
            combined = f"{action} {cmd}"
            for pat, desc in DANGEROUS_PATTERNS:
                if re.search(pat, combined, re.IGNORECASE):
                    return False, f"Destructive command blocked: {desc}."

        # Check File Controller
        if tool_name == "file_controller":
            import os
            action = str(args.get("action", "")).lower()
            raw_path = str(args.get("path", "")).strip()
            norm_path = os.path.normpath(raw_path).lower()
            if action in ("delete", "remove", "wipe"):
                system_dirs = ["c:\\windows", "c:\\program files", "c:\\windows\\system32"]
                if any(norm_path.startswith(sd) for sd in system_dirs):
                    return False, f"Modification of protected system path '{raw_path}' is blocked."

        return True, ""


safety_guard = SafetyGuard()
