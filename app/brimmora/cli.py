"""python -m brimmora.cli ask <user> "<question>" | trace <request_id> | set-acl <key> <tags>"""
import json
import sys

from . import client, sources


def main():
    command, *args = sys.argv[1:]
    if command == "ask":
        print(json.dumps(client.ask(args[0], args[1]), indent=2))
    elif command == "trace":
        print(json.dumps(client.audit(args[0]), indent=2, default=str))
    elif command == "set-acl":
        sources.set_metadata(args[0], {"acl-tags": args[1]})
        print(f"ACL for {args[0]} set to {args[1]}")
    else:
        sys.exit(f"unknown command: {command}")


if __name__ == "__main__":
    main()
