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


