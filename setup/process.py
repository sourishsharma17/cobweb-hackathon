t = eval(open("llm2_output.txt").read())["web_server_files"]

print(t)

import os


for i in t:
    a,b=i["file_path"],i["file_contents"]

    # Ensure the directory exists
    os.makedirs(os.path.dirname(a), exist_ok=True)

    # Write the file
    with open(a, "w") as f:
        f.write(b)

    print(f"File written to {a}")








