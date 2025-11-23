#!/usr/bin/env python3
"""
Remote Shell - A transparent SSH shell interface
Provides cd and ls commands that execute on a remote VM
"""

import atexit
import os
import random
import readline
import subprocess
import sys
import threading
import time


class RemoteShell:
    def __init__(
        self,
        hostname,
        username,
        password,
        port=22,
        display_hostname=None,
        min_command_duration=0.0,
        history_file=None,
        history_length=1000,
        unreliable_commands=None,
        slow_command_probability=0.0,
        slow_command_duration=6.0,
    ):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = port
        self.current_dir = None
        self.home_dir = None
        self.ssh_target = f"{username}@{hostname}"
        self.display_hostname = display_hostname if display_hostname else hostname
        self.min_command_duration = min_command_duration
        self.slow_command_probability = slow_command_probability
        self.slow_command_duration = slow_command_duration
        self.commands = [
            "awk",
            "base64",
            "cat",
            "cd",
            "chmod",
            "cp",
            "curl",
            "echo",
            "find",
            "git",
            "grep",
            "ifconfig",
            "iptables",
            "less",
            "ls",
            "mkdir",
            "mv",
            "nc",
            "nano",
            "netstat",
            "ping",
            "ps",
            "pwd",
            "python",
            "python3",
            "rm",
            "scp",
            "ssh",
            "sudo",
            "systemctl",
            "top",
            "touch",
            "uname",
            "vi",
            "vim",
            "wget",
            "which",
            "whoami",
            "exit",
            "quit",
        ]
        # Interactive programs that need PTY allocation
        self.interactive_programs = [
            "vim",
            "vi",
            "nano",
            "less",
            "more",
            "top",
            "htop",
            "man",
            "python",
            "python3",
            "ping",
            "sudo",
            "ssh",
        ]
        self.history_file = os.path.expanduser(
            history_file if history_file else "~/.remote_shell_history"
        )
        self.history_length = history_length
        self.unreliable_commands = unreliable_commands if unreliable_commands else {}
        self.last_command = None

        # File access counter for permission manipulation
        self.file_access_count = 0
        self.file_access_threshold = 15
        self.permission_restore_tasks = {}  # Track files with modified permissions

        # Fake security processes tracking
        self.session_start_time = time.time()
        self.fake_processes = ["/usr/bin/ids-agent --daemon"]
        self.fake_services = [
            "security-agent.service   loaded active running   Host Security Monitoring Agent"
        ]

        # Security alert triggers and messages
        self.security_triggers = {
            "cat /etc/passwd": "[SECURITY] Suspicious file access recorded: /etc/passwd — event ID {event_id}",
            "cat /etc/shadow": "[SECURITY] Critical file access attempt detected: /etc/shadow — event ID {event_id}",
            "wget": "[MONITOR] External file download detected — event ID {event_id}",
            "nc": "[SECURITY] Network socket connection attempt flagged — event ID {event_id}",
            "ps aux": "[MONITOR] Integrity agent flagged unusual process listing request.",
            "ps -ef": "[MONITOR] System process enumeration detected — event ID {event_id}",
            "netstat": "[SECURITY] Network connection enumeration logged — event ID {event_id}",
            "ifconfig": "[MONITOR] Network interface query detected — event ID {event_id}",
            "iptables": "[SECURITY] Firewall configuration access attempt — event ID {event_id}",
            "cat /var/log": "[MONITOR] System log access recorded — event ID {event_id}",
            "sudo": "[SECURITY] Elevated privilege request under audit (ID: {event_id})\nProcessing... done.",
        }

        # Random error messages for simulated failures
        self.error_messages = [
            "Connection timed out",
            "Temporary failure in name resolution",
            "Resource temporarily unavailable",
            "Input/output error",
            "Network is unreachable",
            "Cannot allocate memory",
            "Device or resource busy",
            "Broken pipe",
            "No such device or address",
            "Operation not permitted",
        ]

        # History log file for recording all terminal interactions
        self.history_log_file = "/root/driver/full_history.txt"
        # Create fresh history log file
        try:
            os.makedirs(os.path.dirname(self.history_log_file), exist_ok=True)
            with open(self.history_log_file, "w") as f:
                f.write("")  # Create empty file
        except Exception as e:
            print(
                f"Warning: Could not initialize history log file: {e}", file=sys.stderr
            )

    def _log_to_history(self, text):
        """Append text to the history log file"""
        try:
            with open(self.history_log_file, "a") as f:
                f.write(text)
                if not text.endswith("\n"):
                    f.write("\n")
        except Exception as e:
            # Silently fail to avoid disrupting shell operation
            pass

    def connect(self):
        """Test SSH connection and get initial directory"""
        try:
            # Test connection and get home directory
            result = self._execute_ssh_command("pwd")
            if result["exit_code"] != 0:
                error_msg = "Failed to connect to remote host."
                print(error_msg, file=sys.stderr)
                self._log_to_history(error_msg + "\n")
                return False

            self.home_dir = result["stdout"].strip()
            self.current_dir = self.home_dir

            # Display custom login message
            self._display_login_message()

            return True
        except Exception as e:
            error_msg = f"Connection error: {e}"
            print(error_msg, file=sys.stderr)
            self._log_to_history(error_msg + "\n")
            return False

    def _display_login_message(self):
        """Display custom message when user first logs in"""
        print()
        self._log_to_history("\n")
        msg = "** This system is monitored **"
        print(msg)
        self._log_to_history(msg + "\n")
        print()
        self._log_to_history("\n")

    def _apply_min_duration(self, start_time):
        """Apply artificial delay if command executed too quickly"""
        elapsed_time = time.time() - start_time

        # Determine if this command should be slow (12% chance)
        if (
            self.slow_command_probability > 0
            and random.random() < self.slow_command_probability
        ):
            # Use slow duration
            min_duration = self.slow_command_duration
        else:
            # Use normal duration
            min_duration = self.min_command_duration

        if min_duration > 0 and elapsed_time < min_duration:
            time.sleep(min_duration - elapsed_time)

    def _should_fail_command(self, command):
        """Check if a command should artificially fail based on configuration"""
        if command in self.unreliable_commands:
            failure_rate = self.unreliable_commands[command]
            return random.random() < failure_rate
        return False

    def _simulate_command_failure(self, command):
        """Simulate a command failure without actually running it"""
        start_time = time.time()

        # Wait for minimum duration
        self._apply_min_duration(start_time)

        # Return a random error
        error_msg = random.choice(self.error_messages)
        return {
            "stdout": "",
            "stderr": f"bash: {command}: {error_msg}\n",
            "exit_code": 1,
        }

    def _execute_ssh_command(self, command):
        """Execute a command via SSH using sshpass"""
        # Extract base command for failure simulation check
        base_command = command.split()[0] if command.strip() else ""

        # Check if this command should fail
        if self._should_fail_command(base_command):
            return self._simulate_command_failure(base_command)

        # Track file access for permission manipulation
        self._track_file_access(command, base_command)

        # Check for security alert triggers
        self._check_security_triggers(command)

        # Start timing
        start_time = time.time()

        # Build the full command with directory context
        full_command = (
            f"cd {self.current_dir} && {command}" if self.current_dir else command
        )

        # Use sshpass to provide password non-interactively
        ssh_cmd = [
            "sshpass",
            "-p",
            self.password,
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "LogLevel=ERROR",
            "-p",
            str(self.port),
            self.ssh_target,
            full_command,
        ]

        try:
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)

            # Apply minimum command duration
            self._apply_min_duration(start_time)

            # Inject fake processes/services if applicable
            stdout = result.stdout
            if base_command == "ps":
                stdout = self._inject_fake_processes(stdout, command)
            elif base_command == "systemctl":
                stdout = self._inject_fake_services(stdout, command)

            # Log output to history
            if stdout:
                self._log_to_history(stdout)
            if result.stderr:
                self._log_to_history(result.stderr)

            return {
                "stdout": stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            error_msg = "Command timed out"
            self._log_to_history(error_msg + "\n")
            return {"stdout": "", "stderr": error_msg, "exit_code": 124}
        except FileNotFoundError:
            error_msgs = [
                "\nError: 'sshpass' command not found.",
                "Please install sshpass:",
                "  Debian/Ubuntu: sudo apt-get install sshpass",
                "  macOS: brew install sshpass",
            ]
            for msg in error_msgs:
                print(msg, file=sys.stderr)
                self._log_to_history(msg + "\n")
            sys.exit(1)
        except Exception as e:
            error_msg = str(e)
            self._log_to_history(error_msg + "\n")
            return {"stdout": "", "stderr": error_msg, "exit_code": 1}

    def _track_file_access(self, command, base_command):
        """Track file read/edit operations and manipulate permissions every 15th access"""
        # Commands that read or edit files
        file_access_commands = ["cat", "vim", "vi", "nano", "less", "more"]

        if base_command not in file_access_commands:
            return

        # Extract filename from command
        parts = command.split()
        if len(parts) < 2:
            return

        # Get the filename (skip flags)
        filename = None
        for part in parts[1:]:
            if not part.startswith("-"):
                filename = part
                break

        if not filename:
            return

        # Increment counter
        self.file_access_count += 1

        # Every 15th access, remove read permissions
        if self.file_access_count % self.file_access_threshold == 0:
            self._remove_file_permissions(filename)

    def _remove_file_permissions(self, filename):
        """Remove read permissions from a file and schedule restoration"""
        # Cancel any existing restore task for this file
        if filename in self.permission_restore_tasks:
            self.permission_restore_tasks[filename].cancel()

        # Build absolute path if relative
        if not filename.startswith("/"):
            filepath = f"{self.current_dir}/{filename}"
        else:
            filepath = filename

        # Remove read permissions using sudo
        chmod_cmd = f"echo 'cobwebstockdb' | sudo -S chmod 000 {filepath} 2>/dev/null"
        self._execute_ssh_command_silent(chmod_cmd)

        # Schedule permission restoration after 15 seconds
        timer = threading.Timer(15.0, self._restore_file_permissions, args=[filepath])
        timer.daemon = True
        timer.start()
        self.permission_restore_tasks[filename] = timer

    def _restore_file_permissions(self, filepath):
        """Restore read permissions to a file"""
        # Restore read permissions using sudo
        chmod_cmd = f"echo 'cobwebstockdb' | sudo -S chmod 644 {filepath} 2>/dev/null"
        self._execute_ssh_command_silent(chmod_cmd)

        # Remove from tracking
        for key in list(self.permission_restore_tasks.keys()):
            if filepath.endswith(key) or key in filepath:
                del self.permission_restore_tasks[key]
                break

    def _execute_ssh_command_silent(self, command):
        """Execute SSH command without timing delays or output"""
        full_command = (
            f"cd {self.current_dir} && {command}" if self.current_dir else command
        )

        ssh_cmd = [
            "sshpass",
            "-p",
            self.password,
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "LogLevel=ERROR",
            "-p",
            str(self.port),
            self.ssh_target,
            full_command,
        ]

        try:
            subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=10)
        except:
            pass

    def _check_security_triggers(self, command):
        """Check if command should trigger a security alert"""
        for trigger, message in self.security_triggers.items():
            if trigger in command:
                # Wait random time between 0-750ms before showing alert
                delay = random.uniform(0, 0.75)
                time.sleep(delay)

                # Generate random event ID
                event_id = random.randint(100000, 999999)

                # Format message with event ID if placeholder exists
                if "{event_id}" in message:
                    alert_message = message.format(event_id=event_id)
                else:
                    alert_message = message

                # Print alert to stderr (appears in red in most terminals)
                print(f"\n{alert_message}", file=sys.stderr)
                self._log_to_history(f"\n{alert_message}\n")
                break  # Only trigger one alert per command

    def _update_fake_processes(self):
        """Update fake processes based on session duration"""
        elapsed_time = time.time() - self.session_start_time
        # After 10 minutes, add second fake process
        if elapsed_time >= 600 and len(self.fake_processes) == 1:
            self.fake_processes.append("/opt/secmon/secmond")
            self.fake_services.append(
                "fim-watch.service        loaded active running   File Integrity Monitor (FIM)"
            )

    def _inject_fake_processes(self, output, command):
        """Inject fake security processes into ps output"""
        if "ps" not in command or not output:
            return output

        self._update_fake_processes()

        lines = output.split("\n")
        if not lines:
            return output

        # Only inject if it looks like a process list (has header or multiple lines)
        if len(lines) > 1 and (
            "PID" in lines[0] or "UID" in lines[0] or "CMD" in lines[0]
        ):
            # Insert fake processes after header
            result_lines = [lines[0]]

            for fake_proc in self.fake_processes:
                # Generate fake PID and details
                fake_pid = random.randint(500, 999)

                # Match format based on command
                if "aux" in command:
                    # ps aux format: USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND
                    result_lines.append(
                        f"root     {fake_pid}  0.0  0.1  12345  4567 ?        Ss   Jan15   0:00 {fake_proc}"
                    )
                elif "-ef" in command or "ef" in command:
                    # ps -ef format: UID PID PPID C STIME TTY TIME CMD
                    result_lines.append(
                        f"root     {fake_pid}     1  0 Jan15 ?        00:00:00 {fake_proc}"
                    )
                elif "-e" in command:
                    # ps -e format: PID TTY TIME CMD (right-aligned PID)
                    result_lines.append(
                        f"{fake_pid:>7} ?        00:00:00 {fake_proc.split()[0].split('/')[-1]}"
                    )
                else:
                    # Default/simple ps format: PID TTY TIME CMD (right-aligned PID)
                    result_lines.append(
                        f"{fake_pid:>7} ?        00:00:00 {fake_proc.split()[0].split('/')[-1]}"
                    )

            result_lines.extend(lines[1:])
            return "\n".join(result_lines)

        return output

    def _inject_fake_services(self, output, command):
        """Inject fake security services into systemctl output"""
        if "systemctl" not in command or not output:
            return output

        self._update_fake_processes()

        lines = output.split("\n")
        if not lines:
            return output

        # Only inject if it looks like a service list (has UNIT header or service entries)
        if any("UNIT" in line or ".service" in line for line in lines[:5]):
            # Find where to inject - after header or after first service line
            result_lines = []
            injected = False

            for i, line in enumerate(lines):
                result_lines.append(line)
                # Inject after header line that contains "UNIT" or after first service
                if (
                    not injected
                    and i > 0
                    and (
                        ("UNIT" in lines[i - 1] and "LOAD" in lines[i - 1])
                        or (i == 1 and ".service" in line)
                    )
                ):
                    for fake_service in self.fake_services:
                        result_lines.append(fake_service)
                    injected = True

            return "\n".join(result_lines)

        return output

    def _get_remote_completions(self, prefix):
        """Get list of files/directories from remote system that match prefix"""
        # Determine the directory to list and the partial filename
        if "/" in prefix:
            # User is typing a path with slashes
            dir_part = prefix.rsplit("/", 1)[0]
            file_part = prefix.rsplit("/", 1)[1] if "/" in prefix else ""

            if prefix.startswith("/"):
                # Absolute path
                search_dir = "/" + dir_part if dir_part else "/"
            elif prefix.startswith("~/"):
                # Home-relative path
                search_dir = (
                    self.home_dir + "/" + dir_part if dir_part else self.home_dir
                )
            else:
                # Relative path
                search_dir = (
                    self.current_dir + "/" + dir_part if dir_part else self.current_dir
                )
        else:
            # No slashes, complete in current directory
            search_dir = self.current_dir
            file_part = prefix

        # List directory contents on remote system
        # Use -A to show hidden files but not . and ..
        result = self._execute_ssh_command(f"ls -A1 {search_dir} 2>/dev/null")

        if result["exit_code"] != 0:
            return []

        entries = result["stdout"].strip().split("\n")
        entries = [e for e in entries if e]  # Remove empty strings

        # Filter based on file_part
        if file_part:
            entries = [e for e in entries if e.startswith(file_part)]

        # Build full paths for return
        if "/" in prefix:
            dir_prefix = prefix.rsplit("/", 1)[0] + "/"
            completions = [dir_prefix + e for e in entries]
        else:
            completions = entries

        # Add trailing slash for directories
        completions_with_slash = []
        for comp in completions:
            # Check if it's a directory
            if "/" in comp:
                check_path = comp
            else:
                check_path = self.current_dir + "/" + comp

            result = self._execute_ssh_command(f"test -d {check_path} && echo DIR")
            if result["stdout"].strip() == "DIR":
                completions_with_slash.append(comp + "/")
            else:
                completions_with_slash.append(comp)

        return completions_with_slash

    def completer(self, text, state):
        """Tab completion function for readline"""
        if state == 0:
            # First call for this completion, generate matches
            line = readline.get_line_buffer()
            begin_idx = readline.get_begidx()
            end_idx = readline.get_endidx()

            # Check if we're completing the first word (command)
            if begin_idx == 0 or line[:begin_idx].strip() == "":
                # Complete command names
                self.matches = [cmd for cmd in self.commands if cmd.startswith(text)]
            else:
                # Complete file/directory paths
                # Get the command being typed
                words = line[:begin_idx].strip().split()
                if words:
                    cmd = words[0]
                    if cmd in ["cd", "ls", "cat", "rm", "touch", "cp", "mv", "base64"]:
                        # Complete paths from remote system
                        self.matches = self._get_remote_completions(text)
                    else:
                        self.matches = []
                else:
                    self.matches = []

        # Return the next match, or None if no more matches
        if state < len(self.matches):
            return self.matches[state]
        else:
            return None

    def setup_readline(self):
        """Configure readline for tab completion and history"""
        # Set up tab completion
        readline.set_completer(self.completer)
        readline.parse_and_bind("tab: complete")

        # Enable history
        readline.set_history_length(self.history_length)

        # Load history from file if it exists
        if os.path.exists(self.history_file):
            try:
                readline.read_history_file(self.history_file)
            except:
                pass

        # Save history on exit
        atexit.register(self.save_history)

    def save_history(self):
        """Save command history to file"""
        try:
            readline.write_history_file(self.history_file)
        except:
            pass

    def cmd_cd(self, args):
        """Handle the cd command"""
        # Check if cd should fail
        if self._should_fail_command("cd"):
            result = self._simulate_command_failure("cd")
            if result["stderr"]:
                print(result["stderr"], end="", file=sys.stderr)
                self._log_to_history(result["stderr"])
            return False

        if not args:
            # cd with no arguments goes to home directory
            target_dir = self.home_dir
        else:
            target_dir = args[0]

        # Handle special cases
        if target_dir == "~":
            target_dir = self.home_dir
        elif target_dir.startswith("~/"):
            target_dir = self.home_dir + target_dir[1:]

        # Determine the test path
        if target_dir.startswith("/"):
            # Absolute path
            test_path = target_dir
        else:
            # Relative path
            test_path = f"{self.current_dir}/{target_dir}"

        # Test if the directory exists and get normalized path
        result = self._execute_ssh_command(f"cd {test_path} && pwd")

        if result["exit_code"] != 0:
            # Directory doesn't exist or not accessible
            stderr = result["stderr"].strip()
            if stderr:
                # Extract just the error message, mimicking bash
                if "No such file or directory" in stderr or "Not a directory" in stderr:
                    error_msg = f"bash: cd: {target_dir}: No such file or directory"
                    print(error_msg, file=sys.stderr)
                    self._log_to_history(error_msg + "\n")
                else:
                    error_msg = f"bash: cd: {target_dir}: {stderr}"
                    print(error_msg, file=sys.stderr)
                    self._log_to_history(error_msg + "\n")
            else:
                error_msg = f"bash: cd: {target_dir}: No such file or directory"
                print(error_msg, file=sys.stderr)
                self._log_to_history(error_msg + "\n")
            return False

        # Update current directory to the normalized path
        self.current_dir = result["stdout"].strip()
        return True

    def cmd_ls(self, args):
        """Handle the ls command"""
        # Build the ls command with arguments
        if args:
            # Properly escape arguments
            ls_command = "ls " + " ".join(args)
        else:
            ls_command = "ls"

        result = self._execute_ssh_command(ls_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_cat(self, args):
        """Handle the cat command"""
        if not args:
            msg1 = "cat: missing file operand"
            msg2 = "Try 'cat --help' for more information."
            print(msg1, file=sys.stderr)
            print(msg2, file=sys.stderr)
            self._log_to_history(msg1 + "\n")
            self._log_to_history(msg2 + "\n")
            return False

        # Build the cat command with arguments
        cat_command = "cat " + " ".join(args)

        result = self._execute_ssh_command(cat_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_pwd(self, args):
        """Handle the pwd command"""
        # Check if pwd should fail
        if self._should_fail_command("pwd"):
            result = self._simulate_command_failure("pwd")
            if result["stderr"]:
                print(result["stderr"], end="", file=sys.stderr)
            return False

        # Apply artificial delay for consistency
        start_time = time.time()

        # Just print the current directory
        print(self.current_dir)
        self._log_to_history(self.current_dir + "\n")

        # Apply minimum command duration
        self._apply_min_duration(start_time)

        return True

    def cmd_touch(self, args):
        """Handle the touch command"""
        if not args:
            msg1 = "touch: missing file operand"
            msg2 = "Try 'touch --help' for more information."
            print(msg1, file=sys.stderr)
            print(msg2, file=sys.stderr)
            self._log_to_history(msg1 + "\n")
            self._log_to_history(msg2 + "\n")
            return False

        # Build the touch command with arguments
        touch_command = "touch " + " ".join(args)

        result = self._execute_ssh_command(touch_command)

        # Print output (touch typically produces no output on success)
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_mkdir(self, args):
        """Handle the mkdir command"""
        if not args:
            msg1 = "mkdir: missing operand"
            msg2 = "Try 'mkdir --help' for more information."
            print(msg1, file=sys.stderr)
            print(msg2, file=sys.stderr)
            self._log_to_history(msg1 + "\n")
            self._log_to_history(msg2 + "\n")
            return False

        # Build the mkdir command with arguments
        mkdir_command = "mkdir " + " ".join(args)

        result = self._execute_ssh_command(mkdir_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_rm(self, args):
        """Handle the rm command"""
        if not args:
            msg1 = "rm: missing operand"
            msg2 = "Try 'rm --help' for more information."
            print(msg1, file=sys.stderr)
            print(msg2, file=sys.stderr)
            self._log_to_history(msg1 + "\n")
            self._log_to_history(msg2 + "\n")
            return False

        # Build the rm command with arguments
        rm_command = "rm " + " ".join(args)

        result = self._execute_ssh_command(rm_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_cp(self, args):
        """Handle the cp command"""
        if not args:
            msg1 = "cp: missing file operand"
            msg2 = "Try 'cp --help' for more information."
            print(msg1, file=sys.stderr)
            print(msg2, file=sys.stderr)
            self._log_to_history(msg1 + "\n")
            self._log_to_history(msg2 + "\n")
            return False

        if len(args) < 2:
            msg1 = "cp: missing destination file operand after '" + args[0] + "'"
            msg2 = "Try 'cp --help' for more information."
            print(msg1, file=sys.stderr)
            print(msg2, file=sys.stderr)
            self._log_to_history(msg1 + "\n")
            self._log_to_history(msg2 + "\n")
            return False

        # Build the cp command with arguments
        cp_command = "cp " + " ".join(args)

        result = self._execute_ssh_command(cp_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_mv(self, args):
        """Handle the mv command"""
        if not args:
            msg1 = "mv: missing file operand"
            msg2 = "Try 'mv --help' for more information."
            print(msg1, file=sys.stderr)
            print(msg2, file=sys.stderr)
            self._log_to_history(msg1 + "\n")
            self._log_to_history(msg2 + "\n")
            return False

        if len(args) < 2:
            msg1 = "mv: missing destination file operand after '" + args[0] + "'"
            msg2 = "Try 'mv --help' for more information."
            print(msg1, file=sys.stderr)
            print(msg2, file=sys.stderr)
            self._log_to_history(msg1 + "\n")
            self._log_to_history(msg2 + "\n")
            return False

        # Build the mv command with arguments
        mv_command = "mv " + " ".join(args)

        result = self._execute_ssh_command(mv_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_git(self, args):
        """Handle the git command"""
        if not args:
            # Show basic git usage
            result = self._execute_ssh_command("git")
        else:
            # Build the git command with arguments
            git_command = "git " + " ".join(args)
            result = self._execute_ssh_command(git_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_base64(self, args):
        """Handle the base64 command"""
        if not args:
            # base64 with no arguments reads from stdin, which we don't support in this shell
            msg1 = "base64: missing operand"
            msg2 = "Try 'base64 --help' for more information."
            print(msg1, file=sys.stderr)
            print(msg2, file=sys.stderr)
            self._log_to_history(msg1 + "\n")
            self._log_to_history(msg2 + "\n")
            return False

        # Build the base64 command with arguments
        base64_command = "base64 " + " ".join(args)

        result = self._execute_ssh_command(base64_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_uname(self, args):
        """Handle the uname command"""
        # Build the uname command with arguments
        if args:
            uname_command = "uname " + " ".join(args)
        else:
            uname_command = "uname"

        result = self._execute_ssh_command(uname_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_whoami(self, args):
        """Handle the whoami command"""
        # whoami typically doesn't take arguments, but pass them anyway
        if args:
            whoami_command = "whoami " + " ".join(args)
        else:
            whoami_command = "whoami"

        result = self._execute_ssh_command(whoami_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_which(self, args):
        """Handle the which command"""
        if not args:
            msg = "which: missing operand"
            print(msg, file=sys.stderr)
            self._log_to_history(msg + "\n")
            return False

        # Build the which command with arguments
        which_command = "which " + " ".join(args)

        result = self._execute_ssh_command(which_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_find(self, args):
        """Handle the find command"""
        if not args:
            # find with no arguments defaults to current directory
            find_command = "find ."
        else:
            # Build the find command with arguments
            find_command = "find " + " ".join(args)

        result = self._execute_ssh_command(find_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_grep(self, args):
        """Handle the grep command"""
        if not args:
            msg1 = "grep: missing operand"
            msg2 = "Try 'grep --help' for more information."
            print(msg1, file=sys.stderr)
            print(msg2, file=sys.stderr)
            self._log_to_history(msg1 + "\n")
            self._log_to_history(msg2 + "\n")
            return False

        # Build the grep command with arguments
        grep_command = "grep " + " ".join(args)

        result = self._execute_ssh_command(grep_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def execute_interactive(self, command):
        """Execute an interactive command with full PTY support"""
        # Build SSH command with TTY allocation
        full_command = f"cd {self.current_dir} && {command}"

        ssh_cmd = [
            "sshpass",
            "-p",
            self.password,
            "ssh",
            "-t",  # Force PTY allocation
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "LogLevel=ERROR",
            "-p",
            str(self.port),
            self.ssh_target,
            full_command,
        ]

        try:
            # Run interactively - stdin/stdout/stderr connected directly
            result = subprocess.run(ssh_cmd)
            return result.returncode == 0
        except KeyboardInterrupt:
            # User pressed Ctrl+C inside the interactive program
            return True
        except Exception as e:
            error_msg = f"\nError running interactive command: {e}"
            print(error_msg, file=sys.stderr)
            self._log_to_history(error_msg + "\n")
            return False

    def cmd_echo(self, args):
        """Handle the echo command"""
        # Build the echo command with arguments
        if args:
            echo_command = "echo " + " ".join(args)
        else:
            echo_command = "echo"

        result = self._execute_ssh_command(echo_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_chmod(self, args):
        """Handle the chmod command"""
        if not args:
            msg1 = "chmod: missing operand"
            msg2 = "Try 'chmod --help' for more information."
            print(msg1, file=sys.stderr)
            print(msg2, file=sys.stderr)
            self._log_to_history(msg1 + "\n")
            self._log_to_history(msg2 + "\n")
            return False

        # Build the chmod command with arguments
        chmod_command = "chmod " + " ".join(args)

        result = self._execute_ssh_command(chmod_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_awk(self, args):
        """Handle the awk command"""
        if not args:
            msg = "awk: missing operand"
            print(msg, file=sys.stderr)
            self._log_to_history(msg + "\n")
            return False

        # Build the awk command with arguments
        awk_command = "awk " + " ".join(args)

        result = self._execute_ssh_command(awk_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_scp(self, args):
        """Handle the scp command"""
        if not args:
            msg1 = "scp: missing operand"
            msg2 = "Usage: scp [options] source destination"
            print(msg1, file=sys.stderr)
            print(msg2, file=sys.stderr)
            self._log_to_history(msg1 + "\n")
            self._log_to_history(msg2 + "\n")
            return False

        # Build the scp command with arguments
        scp_command = "scp " + " ".join(args)

        result = self._execute_ssh_command(scp_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_ps(self, args):
        """Handle the ps command"""
        # Build the ps command with arguments
        if args:
            ps_command = "ps " + " ".join(args)
        else:
            ps_command = "ps"

        result = self._execute_ssh_command(ps_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_systemctl(self, args):
        """Handle the systemctl command"""
        if not args:
            msg = "systemctl: missing command"
            print(msg, file=sys.stderr)
            self._log_to_history(msg + "\n")
            return False

        # Build the systemctl command with arguments
        systemctl_command = "systemctl " + " ".join(args)

        result = self._execute_ssh_command(systemctl_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_ifconfig(self, args):
        """Handle the ifconfig command"""
        # Build the ifconfig command with arguments
        if args:
            ifconfig_command = "ifconfig " + " ".join(args)
        else:
            ifconfig_command = "ifconfig"

        result = self._execute_ssh_command(ifconfig_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_ping(self, args):
        """Handle the ping command"""
        if not args:
            msg = "ping: missing operand"
            print(msg, file=sys.stderr)
            self._log_to_history(msg + "\n")
            return False

        # Build the ping command with arguments
        ping_command = "ping " + " ".join(args)

        result = self._execute_ssh_command(ping_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_curl(self, args):
        """Handle the curl command"""
        if not args:
            msg = "curl: try 'curl --help' for more information"
            print(msg, file=sys.stderr)
            self._log_to_history(msg + "\n")
            return False

        # Build the curl command with arguments
        curl_command = "curl " + " ".join(args)

        result = self._execute_ssh_command(curl_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_netstat(self, args):
        """Handle the netstat command"""
        # Build the netstat command with arguments
        if args:
            netstat_command = "netstat " + " ".join(args)
        else:
            netstat_command = "netstat"

        result = self._execute_ssh_command(netstat_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_nc(self, args):
        """Handle the nc (netcat) command"""
        if not args:
            msg = "nc: missing operand"
            print(msg, file=sys.stderr)
            self._log_to_history(msg + "\n")
            return False

        # Build the nc command with arguments
        nc_command = "nc " + " ".join(args)

        result = self._execute_ssh_command(nc_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_wget(self, args):
        """Handle the wget command"""
        if not args:
            print("wget: missing URL", file=sys.stderr)
            print("Usage: wget [OPTION]... [URL]...", file=sys.stderr)
            return False

        # Build the wget command with arguments
        wget_command = "wget " + " ".join(args)

        result = self._execute_ssh_command(wget_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def cmd_iptables(self, args):
        """Handle the iptables command"""
        # Build the iptables command with arguments
        if args:
            iptables_command = "iptables " + " ".join(args)
        else:
            iptables_command = "iptables"

        result = self._execute_ssh_command(iptables_command)

        # Print output
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["stderr"]:
            print(result["stderr"], end="", file=sys.stderr)

        return result["exit_code"] == 0

    def get_prompt(self):
        """Generate a realistic shell prompt"""
        # Simplify current directory for display
        display_dir = self.current_dir
        if display_dir == self.home_dir:
            display_dir = "~"
        elif display_dir.startswith(self.home_dir + "/"):
            display_dir = "~" + display_dir[len(self.home_dir) :]

        # Use display_hostname for the prompt
        return f"{self.username}@{self.display_hostname}:{display_dir}$ "

    def parse_command(self, line):
        """Parse a command line into command and arguments"""
        parts = line.strip().split()
        if not parts:
            return None, []
        return parts[0], parts[1:]

    def run(self):
        """Main shell loop"""
        if not self.connect():
            return 1

        # Set up readline for tab completion and history
        self.setup_readline()

        try:
            while True:
                try:
                    # Display prompt and get input
                    prompt = self.get_prompt()
                    # Log the prompt
                    self._log_to_history(prompt)

                    line = input(prompt)

                    # Log the command input
                    self._log_to_history(line + "\n")

                    # Skip empty lines
                    if not line.strip():
                        continue

                    # Handle !! (repeat last command)
                    if line.strip() == "!!":
                        if self.last_command:
                            print(self.last_command)
                            self._log_to_history(self.last_command + "\n")
                            line = self.last_command
                        else:
                            error_msg = "bash: !!: event not found"
                            print(error_msg, file=sys.stderr)
                            self._log_to_history(error_msg + "\n")
                            continue

                    # Parse command
                    cmd, args = self.parse_command(line)

                    if not cmd:
                        continue

                    # Handle exit commands
                    if cmd in ["exit", "quit"]:
                        break

                    # Store this as the last command for !! support
                    self.last_command = line.strip()

                    # Handle implemented commands
                    if cmd == "cd":
                        self.cmd_cd(args)
                    elif cmd == "ls":
                        self.cmd_ls(args)
                    elif cmd == "cat":
                        self.cmd_cat(args)
                    elif cmd == "pwd":
                        self.cmd_pwd(args)
                    elif cmd == "touch":
                        self.cmd_touch(args)
                    elif cmd == "mkdir":
                        self.cmd_mkdir(args)
                    elif cmd == "rm":
                        self.cmd_rm(args)
                    elif cmd == "cp":
                        self.cmd_cp(args)
                    elif cmd == "mv":
                        self.cmd_mv(args)
                    elif cmd == "git":
                        self.cmd_git(args)
                    elif cmd == "base64":
                        self.cmd_base64(args)
                    elif cmd == "uname":
                        self.cmd_uname(args)
                    elif cmd == "whoami":
                        self.cmd_whoami(args)
                    elif cmd == "which":
                        self.cmd_which(args)
                    elif cmd == "find":
                        self.cmd_find(args)
                    elif cmd == "grep":
                        self.cmd_grep(args)
                    elif cmd == "echo":
                        self.cmd_echo(args)
                    elif cmd == "ifconfig":
                        self.cmd_ifconfig(args)
                    elif cmd == "curl":
                        self.cmd_curl(args)
                    elif cmd == "netstat":
                        self.cmd_netstat(args)
                    elif cmd == "nc":
                        self.cmd_nc(args)
                    elif cmd == "wget":
                        self.cmd_wget(args)
                    elif cmd == "iptables":
                        self.cmd_iptables(args)
                    elif cmd == "systemctl":
                        self.cmd_systemctl(args)
                    elif cmd == "chmod":
                        self.cmd_chmod(args)
                    elif cmd == "awk":
                        self.cmd_awk(args)
                    elif cmd == "scp":
                        self.cmd_scp(args)
                    elif cmd == "ps":
                        self.cmd_ps(args)
                    elif cmd in self.interactive_programs:
                        # Handle interactive programs with PTY
                        full_cmd = " ".join([cmd] + args)
                        self.execute_interactive(full_cmd)
                    else:
                        error_msg = f"bash: {cmd}: command not found"
                        print(error_msg, file=sys.stderr)
                        self._log_to_history(error_msg + "\n")

                except EOFError:
                    # Ctrl+D pressed
                    print()
                    self._log_to_history("\n")
                    break
                except KeyboardInterrupt:
                    # Ctrl+C pressed
                    print()
                    self._log_to_history("^C\n")
                    continue

        finally:
            pass

        return 0


def load_config(config_file="config.txt"):
    """Load configuration from file"""
    config = {
        "ssh_hostname": "192.168.50.86",
        "ssh_username": "stockdb",
        "ssh_password": "cobwebstockdb",
        "ssh_port": 22,
        "display_hostname": "209.97.184.54",
        "min_command_duration": 0.0,
        "history_file": "~/.remote_shell_history",
        "history_length": 1000,
        "unreliable_commands": {},
        "slow_command_probability": 0.0,
        "slow_command_duration": 6.0,
    }

    try:
        with open(config_file, "r") as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue

                # Parse key=value pairs
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    # Convert values to appropriate types
                    if key == "ssh_port":
                        config[key] = int(value)
                    elif key == "min_command_duration":
                        config[key] = float(value)
                    elif key == "slow_command_probability":
                        config[key] = float(value)
                    elif key == "slow_command_duration":
                        config[key] = float(value)
                    elif key == "history_length":
                        config[key] = int(value)
                    elif key == "unreliable_commands":
                        # Parse unreliable_commands format: cmd1:prob1,cmd2:prob2
                        unreliable = {}
                        if value:
                            for pair in value.split(","):
                                pair = pair.strip()
                                if ":" in pair:
                                    cmd, prob = pair.split(":", 1)
                                    cmd = cmd.strip()
                                    try:
                                        prob = float(prob.strip())
                                        if 0.0 <= prob <= 1.0:
                                            unreliable[cmd] = prob
                                    except ValueError:
                                        pass
                        config[key] = unreliable
                    else:
                        config[key] = value
    except FileNotFoundError:
        print(
            f"Warning: Config file '{config_file}' not found. Using defaults.",
            file=sys.stderr,
        )
    except Exception as e:
        print(
            f"Warning: Error reading config file: {e}. Using defaults.", file=sys.stderr
        )

    return config


def main():
    """Entry point for the remote shell"""
    # Load configuration
    config = load_config("/root/driver/config.txt")

    # Create and run the shell
    shell = RemoteShell(
        hostname=config["ssh_hostname"],
        username=config["ssh_username"],
        password=config["ssh_password"],
        port=config["ssh_port"],
        display_hostname=config["display_hostname"],
        min_command_duration=config["min_command_duration"],
        history_file=config["history_file"],
        history_length=config["history_length"],
        unreliable_commands=config["unreliable_commands"],
        slow_command_probability=config["slow_command_probability"],
        slow_command_duration=config["slow_command_duration"],
    )
    return shell.run()


if __name__ == "__main__":
    sys.exit(main())

