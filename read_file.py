import json

def parse_jsonc(path: str) -> dict:
  file = open(path, "r", encoding="utf-8")
  jsonc_lines = file.readlines()
  file.close()
  json_str = ""
  for line in jsonc_lines:
    json_line = line.split("//")[0].strip()
    json_str += json_line + "\n"
  return json.loads(json_str)

def join_last_arg(str_list: list, split_char=";") -> str:
  ans = str_list[0]
  for i in range(1, len(str_list)):
    ans += ";" + str_list[i]
  return ans

def parse_command(command: str) -> dict:
  segments = command.split(";")
  id = segments[0]
  command = segments[1]
  command_type = "T"
  args = []
  if id == "C":
    command_type = "C"
  if command in ["READ", "CAN_COMMIT", "READ_POSSIBLE_VALUES", "READ_COMMIT"]:
    args = [join_last_arg(segments[2:])]
  elif command == "WRITE":
    last = join_last_arg(segments[2:]).split(",")
    args = [last[0], join_last_arg(last[1:], ",")]
  return {"id": id, "command": command, "type": command_type, "args": args}
