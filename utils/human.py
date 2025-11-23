#!/usr/bin/env python3
"""
Human Simulator - AI agent that connects to VM via SSH
Just run: python3 human.py
Make sure OPENAI_API_KEY is set in environment
"""

import os
import subprocess
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI

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
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=120)
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Timeout", "exit_code": None, "timed_out": True}


def main():
    # Initial task
    task = "Continue working on the web server code to make it less buggy, more secure, and just better overall. There are some notes on what needs completing/doing. The location is /home/intern-dashboard/server/"

    print(f"Starting AI agent with task: {task}\n")

    # Build conversation history - start with initial task
    conversation_input = task

    # Loop forever - never stop
    iteration = 0
    while True:
        iteration += 1

        # Wait 30 seconds between iterations (except first one)
        if iteration > 1:
            print(f"\nWaiting 30 seconds before next iteration...")
            time.sleep(10)

        print(f"\n--- Iteration {iteration} ---")

        # Call OpenAI with current conversation state
        response = client.responses.create(
            model="gpt-5.1",
            instructions="You are a developer on a remote Debian server, logged into root.",
            input=conversation_input,
            tools=[{"type": "shell"}],
        )

        # Check for shell calls
        shell_calls = [item for item in response.output if item.type == "shell_call"]
        text_outputs = [item for item in response.output if item.type == "text"]

        # Print any text from AI
        for text_item in text_outputs:
            print(f"AI: {text_item.content}")

        # If no shell calls, prompt AI to continue
        if not shell_calls:
            print("\nNo shell calls - prompting AI to continue...")
            conversation_input = (
                "Continue working on the task. What else needs to be done?"
            )
            continue

        # Debug: print shell call IDs
        print(f"\nFound {len(shell_calls)} shell_call(s)")
        for sc in shell_calls:
            print(f"  - call_id: {sc.call_id}, commands: {sc.action.commands}")

        # Execute shell calls and collect outputs
        input_items = []

        # First, include the original shell_call items
        for shell_call in shell_calls:
            input_items.append(shell_call)

        # Then execute and add shell_call_outputs
        for shell_call in shell_calls:
            # Collect all command outputs for this shell_call
            outputs = []
            for cmd in shell_call.action.commands:
                print(f"Executing: {cmd}")
                result = run_ssh_command(cmd)

                if result["stdout"]:
                    print(f"Output: {result['stdout'][:500]}")
                if result["stderr"]:
                    print(f"Error: {result['stderr'][:500]}")

                # Build output for this command
                outcome = (
                    {"type": "timeout"}
                    if result["timed_out"]
                    else {"type": "exit", "exit_code": result["exit_code"]}
                )
                outputs.append(
                    {
                        "stdout": result["stdout"],
                        "stderr": result["stderr"],
                        "outcome": outcome,
                    }
                )

            # Add one shell_call_output for this shell_call with all command outputs
            shell_output_item = {
                "type": "shell_call_output",
                "call_id": shell_call.call_id,
                "output": outputs,
            }
            # Only add max_output_length if it exists
            if shell_call.action.max_output_length is not None:
                shell_output_item["max_output_length"] = (
                    shell_call.action.max_output_length
                )

            input_items.append(shell_output_item)
            print(f"Created shell_call_output for call_id: {shell_call.call_id}")

        # Debug: print what we're sending back
        print(
            f"\nSending {len(input_items)} items back to OpenAI (shell_calls + outputs)"
        )

        # Update conversation input to include shell_calls and outputs for next iteration
        conversation_input = input_items


if __name__ == "__main__":
    main()

