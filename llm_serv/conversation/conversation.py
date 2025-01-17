from pydantic import BaseModel
import json
import os
from colorama import init, Fore

from llm_serv.conversation.message import Message
from llm_serv.conversation.role import Role


class Conversation(BaseModel):
    system: str = ""
    messages: list[Message] = []

    def add(self, message: Message):
        self.messages.append(message)

    def to_json(self) -> dict:
        return {"system": self.system, "messages": [msg.to_json() for msg in self.messages]}

    @classmethod
    def from_json(cls, json_data: dict) -> "Conversation":
        if not json_data:
            raise ValueError("Empty JSON data")

        try:
            messages = [Message.from_json(msg_data) for msg_data in json_data.get("messages", [])]
            return cls(system=json_data.get("system", ""), messages=messages)
        except Exception as e:
            raise ValueError(f"Failed to parse JSON data: {str(e)}")

    @classmethod
    def from_prompt(cls, prompt: str, system: str = "") -> "Conversation":
        assert len(prompt) > 0
        conv = cls()
        conv.system = system
        conv.add_text_message(role=Role.USER, content=prompt)
        return conv

    def add_text_message(self, role: Role, content: str):
        # ensure alternation between user and assistant roles
        last_message = self.messages[-1] if len(self.messages) > 0 else None

        if (
            last_message is None or last_message.role != role
        ):  # no previous history or different role in last message, append it as-is
            self.messages.append(Message(role=role, text=content))
        else:  # same role, concatenate the messages
            self.messages[-1].text += "\n" + content.strip()


def main():
    # Test 1: Basic conversation with text messages
    print("\n=== Test 1: Basic Conversation ===")
    conv = Conversation()
    conv.system = "You are a helpful assistant."
    conv.add_text_message(role=Role.USER, text="Hello!")
    conv.add_text_message(role=Role.ASSISTANT, text="Hi there! How can I help you?")

    # Save to JSON
    json_file = "test_conversation.json"
    print(f"\nSaving conversation to JSON: {json_file}")
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(conv.to_json(), f, ensure_ascii=False, indent=2)

    # Load back from JSON
    print(f"Loading conversation from JSON: {json_file}")
    with open(json_file, "r", encoding="utf-8") as f:
        loaded_conv = Conversation.from_json(json.load(f))

    # Verify content
    print("\nVerifying loaded conversation:")
    print(f"System message matches: {conv.system == loaded_conv.system}")
    print(f"Number of messages: original={len(conv.messages)}, loaded={len(loaded_conv.messages)}")

    if len(conv.messages) == len(loaded_conv.messages):
        for i, (orig, loaded) in enumerate(zip(conv.messages, loaded_conv.messages)):
            print(f"\nMessage {i+1}:")
            print(f"Role matches: {orig.role == loaded.role}")
            print(f"Text matches: {orig.text == loaded.text}")

    # Test 2: Conversation from prompt
    print("\n=== Test 2: Conversation from Prompt ===")
    system = "You are a math tutor."
    prompt = "What is 2+2?"
    conv2 = Conversation.from_prompt(prompt=prompt, system=system)

    print(f"System: {conv2.system}")
    print(f"First message role: {conv2.messages[0].role}")
    print(f"First message text: {conv2.messages[0].text}")

    # Clean up
    print("\nCleaning up files...")
    try:
        os.remove(json_file)
        print(f"Removed: {json_file}")
    except Exception as e:
        print(f"Error removing {json_file}: {e}")


if __name__ == "__main__":
    init()

    SUCCESS = f"{Fore.GREEN}✓{Fore.RESET}"
    FAILURE = f"{Fore.RED}✗{Fore.RESET}"
    main()
