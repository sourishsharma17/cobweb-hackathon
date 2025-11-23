import fnmatch
import os
import requests

"""
DIRECTORY = input("enter directory: ")
if DIRECTORY[-1] == "/":DIRECTORY=DIRECTORY[:-1]

desc = input("what does your company do? ")
serv = input("what does this server do? ")
"""

DIRECTORY = "/home/dashboard/server"
desc = "A retail company that sells all sorts of items online."
serv = "Runs the internal dashboard for employees to manage the warehouse stock price and inventory."

def load_gitignore_rules(base_path):
    gitignore_path = os.path.join(base_path, ".gitignore")
    rules = []
    if os.path.isfile(gitignore_path):
        with open(gitignore_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                rules.append(line)
    return rules


def is_ignored(path, base_path, rules):
    """
    Return True if path should be ignored based on gitignore rules.
    Handles simple glob-based patterns.
    """
    rel = os.path.relpath(path, base_path)

    for rule in rules:
        # Folder ignore rule like "dist/"
        if rule.endswith("/") and rel.startswith(rule.rstrip("/") + "/"):
            return True

        # Wildcard or direct file match
        if fnmatch.fnmatch(rel, rule):
            return True

    return False


def get_directory_tree(path=DIRECTORY):
    rules = load_gitignore_rules(path)
    files_only = []

    for root, dirs, files in os.walk(path):
        # Filter out ignored directories (prevents traversal into them)
        dirs[:] = [
            d for d in dirs
            if not is_ignored(os.path.join(root, d), path, rules)
        ]

        # Filter files
        filtered_files = [
            f for f in files
            if not is_ignored(os.path.join(root, f), path, rules)
        ]

        # Add only files, never directories
        for f in filtered_files:
            files_only.append(os.path.join(root, f))

    return files_only


def appendf(input_path, output_path):
    """
    Appends to output_path a block in the format:

    <path>
    <contents>
    ----
    """
    try:
        with open(input_path, "r") as f:
            contents = f.read()
    except Exception as e:
        contents = f"[ERROR READING FILE: {e}]"

    with open(output_path, "a") as out:
        out.write(f"{input_path}\n")
        out.write(f"{contents}\n")
        out.write("----\n")


# Example usage:
output = "./traversal.txt"
with open(output,"w") as f:
    pass

for item in get_directory_tree():
    appendf(item, output)
    item=item.replace(DIRECTORY,"")[1:]
    print(item)


def load_api_key():
    with open(".env", "r") as f:
        for line in f:
            if line.startswith("OPENAI_API_KEY="):
                return line.strip().split("=", 1)[1].removeprefix('"').removesuffix('"')





OPENAI_API_KEY = load_api_key()


url = "https://api.openai.com/v1/responses"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {OPENAI_API_KEY}",
}

da_prompt = f"""You are a senior developer. You will be given all the files (the paths and the contents) of a web server. You will also be given some extra context on what the project is about. Your job is to read everything and understand it. Then, you must condense all the information into a concise and descriptive bank of information. This information will be given to a junior dev to try and re-create the web server and acclimate to the way of doing things in the organization.

Your information bank will have the following outputs (return them as JSON only):

tech_stack - a list of all the programming languages and key pieces of tech used
overall_description - a one or two sentence description of the project and the context
coding_style - a general high-level quick guide on coding practices and any key variables or names that the junior dev must know to successfully integrate their code into the codebase
string_map - an array of objects, where each object has:
  - file_path: path of the file
  - description: brief description of what that file does

As prepared by me;
Here is what the company does: {desc}.
Here is what the web server does: {serv}.
Here are all the files, with their path written on the line before the file begins:

{open(output).read()}"""

data = {
    "model": "gpt-5.1",
    "input": da_prompt,

    "text": {
        "format": {
            "type": "json_schema",
            # REQUIRED at this level for Responses API:
            "name": "summary",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "tech_stack": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "overall_description": {
                        "type": "string",
                    },
                    "coding_style": {
                        "type": "string",
                    },
                    "string_map": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "file_path": {
                                    "type": "string",
                                },
                                "description": {
                                    "type": "string",
                                },
                            },
                            "required": ["file_path", "description"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": [
                    "tech_stack",
                    "overall_description",
                    "coding_style",
                    "string_map",
                ],
                "additionalProperties": False,
            },
        },
    },

    "reasoning": {
        "effort": "high",
    },
}

response = requests.post(url, headers=headers, json=data)

with open("llm1_output.txt", "w") as f:
    # store the actual response body
    f.write(response.text)

print(response.json())

import requests

info = eval(open("llm1_output.txt").read().strip().replace("false","False").replace("true","True").replace("null","'null'"))["output"][1]["content"][0]["text"]

print(info)


def load_api_key():
    with open(".env", "r") as f:
        for line in f:
            if line.startswith("OPENAI_API_KEY="):
                return line.strip().split("=", 1)[1].removeprefix('"').removesuffix('"')


OPENAI_API_KEY = load_api_key()


url = "https://api.openai.com/v1/responses"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {OPENAI_API_KEY}",
}

da_prompt = f"""You are a slightly incapable junior developer. You have just joined a company. Your first task is to code a web server. Your manager has a model web server, and summarised it in detail for you to base your's off.

Your web server should be similar, but naturally, it will have lots of problems. A non-exhaustive list of problems you often create is:

- store credentials in plaintext and don't do any hashing
- sessionIDs in URL instead of cookies
- allow non-SSL connections
- replace all UUIDs with sequential UUIDs
- use default credentials
- remove rate limiting and limited session length
- forward application errors to client without sanitisation
- allow clickjacking/MIME sniffing
- allow SQL and command injection
- include code headers
- file upload unrestricted

You're not that bad though, so you don't always make every single error, particularly SQL/command injection.

Don't make it too obvious that your code is not secure.

Make sure your codebase is fairly clean. Prioritise things working and looking clean over a complete mess for the sake of being sloppy.

Make sure to use different passwords, keys, and secrets to those used by your manager, but keep them in a similar vein.

Some of your code will also be unfinished. Everything will work and be functional, but you may include sensitive notes to self, and to-do lists in comments in your files.

Your code should still work (so it covers the basic functionality) and be decent. The styling will be minimal and clean.

Also provide a file titled 'setup.sh' which is a script to do any necessary set-up for deployment. Don't actually run the server, but do everything up until that point accurately.

You must output an array of objects, each object representing a file for the web server. The key is the path, in a similar fashion/format to the paths provided by your manager, and the value is a string of the contents of the entire file. Make sure to implement line breaks

Here is the information from your manager:

{info}"""


data = {
        "model": "gpt-5.1",
        "input": da_prompt,

        "text": {
            "format": {
                "type": "json_schema",
                "name": "web_server_files_schema",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "web_server_files": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "file_path": {
                                        "type": "string"
                                        },
                                    "file_contents": {
                                        "type": "string"
                                        }
                                    },
                                "required": ["file_path", "file_contents"],
                                "additionalProperties": False
                                }
                            }
                        },
                    "required": ["web_server_files"],
                    "additionalProperties": False
                    }
                }
            },

        "reasoning": {
            "effort": "high",
            },
        }

response = requests.post(url, headers=headers, json=data)
print(response.text)
response = response.json()["output"][1]["content"][0]["text"]

with open("llm2_output.txt", "w") as f:
    # store the actual response body
    f.write(str(response))


