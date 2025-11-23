# 🕸️ Cobweb - AI-Powered Honeypot Deception System

> **Flip the script on attackers.** An intelligent honeypot that psychologically manipulates attackers into giving up.

## 🎯 The Core Idea

Most honeypots passively log attacks. **Cobweb actively deters them.** When an attacker compromises the system, they're greeted with a psychologically-crafted README that makes them believe they've been caught, tracked, and identified, using applied psychology inspired by fortune tellers.

## ⚡ How It Works

**1. Auto-Generate Vulnerable Servers** 🤖  
LLM reads a secure reference server → generates an intentionally broken version with realistic vulnerabilities (plaintext creds, SQL injection, weak sessions). It's messy enough to be believable, clean enough to look production-ready.

**2. Transparent SSH Honeypot** 🎭  
Attackers interact with what *feels* like a real Linux shell. Behind the scenes:
- Commands proxy to an actual VM via SSH
- Fake security processes appear in `ps` output
- File permissions randomly break (then mysteriously fix themselves)
- Random "security alerts" trigger on suspicious commands
- Everything gets logged for analysis

**3. Psychological Warfare README** 🧠  
When the attacker is deep enough, an LLM analyzes their command history and generates a personalized "SECURITY NOTICE" that:
- Quotes their exact commands back at them
- Fabricates plausible tracking data (fake timestamps, session IDs)
- Uses Barnum statements to feel eerily specific
- **Never** reveals it's a honeypot—just a "monitored production system"
- Primes confirmation bias: "Your use of [specific tool] suggests systematic reconnaissance"

## 🛠️ Key Components

- **`setup/condenser.py`** - Scans a real server, extracts structure for LLM analysis
- **`setup/expander.py`** - Feeds LLM a "manager's notes," gets back sloppy junior dev code (with vulns)
- **`utils/main.py`** - The honeypot shell that proxies commands while injecting chaos
- **`utils/llm_prompt.txt`** - Psychological deception framework for generating attacker-specific notices
- **`example-webserver/`** - Reference implementation of an internal dashboard (what the LLM copies/breaks)

## 🎪 Cool Features

**Adaptive Chaos**
- 12% of commands randomly slow down (simulates network lag)
- Files lose permissions after 15 accesses (auto-restore after 15s)
- Fake security daemons (`ids-agent`, `fim-watch.service`) appear mid-session

**Believable Vulnerabilities**
- Sequential UUIDs instead of random ones
- Plaintext passwords in configs
- Session IDs in URLs
- SQL/command injection opportunities (not too obvious)
- Unfinished TODOs in code comments

**Smart Logging**
- Full command history saved for forensic analysis
- LLM ingests logs to build attacker profiles
- Detects skill level from command sophistication

## 🚀 Quick Start

```bash
# On your secure reference server:
cd setup
python3 condex.py

# In your sandboxed VM:
cd setup
python3 process.py

# Start the honeypot shell
cd utils
python3 main.py
```