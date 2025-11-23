import os
import subprocess

import openai
from dotenv import load_dotenv

load_dotenv()
client = openai.Client(api_key=os.getenv("OPENAI_API_KEY"))

# VM connection details
HOSTNAME = "192.168.50.86"
USERNAME = "stockdb"
PASSWORD = "cobwebstockdb"
PORT = 22


def run_ssh_command(command):
  """Execute a command on the VM via SSH"""
  ssh_cmd = [
      "sshpass",
      "-p",
      PASSWORD,
      "ssh",
      "-o",
      "StrictHostKeyChecking=no",
      "-o",
      "UserKnownHostsFile=/dev/null",
      "-o",
      "LogLevel=ERROR",
      "-p",
      str(PORT),
      f"{USERNAME}@{HOSTNAME}",
      command,
  ]

  try:
    result = subprocess.run(
      ssh_cmd, capture_output=True, text=True, timeout=120)
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.returncode,
        "timed_out": False,
    }
  except subprocess.TimeoutExpired:
    return {"stdout": "", "stderr": "Timeout", "exit_code": None, "timed_out": True}


prompt_path = os.path.join(os.path.dirname(__file__), "llm_prompt.txt")
with open(prompt_path, "r", encoding="utf-8") as f:
  prompt = f.read()

sample_data_path = os.path.join(os.path.dirname(__file__), "full_history.txt")
with open(sample_data_path, "r", encoding="utf-8") as f:
  data = f.read()

response = client.responses.create(
  model="gpt-5.1",
  instructions=prompt,
  reasoning={"effort": "none"},
  input=data
)

output_text = response.output_text
print(output_text)

# Save output to VM
print("\nSaving to VM at /home/stockdb/README.txt...")
# Escape single quotes in the output text and write to file on VM
escaped_output = output_text.replace("'", "'\"'\"'")
command = f"echo '{escaped_output}' > /home/stockdb/README.txt"
result = run_ssh_command(command)

if result["exit_code"] == 0:
  print("Successfully saved to VM!")
else:
  print(f"Error saving to VM: {result['stderr']}")
