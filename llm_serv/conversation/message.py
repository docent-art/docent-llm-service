from typing import Optional

from pydantic import BaseModel, Field, model_validator
from colorama import init, Fore

from llm_serv.conversation.role import Role
from llm_serv.conversation.document import Document
from llm_serv.conversation.image import Image


class Message(BaseModel):
    model_config = {
        "arbitrary_types_allowed": True,
        "json_encoders": {
            Image: lambda img: img.to_json()
        }
    }

    role: Role = Field(default=Role.USER)
    text: Optional[str] = None
    images: list[Image] = Field(default_factory=list)
    # documents: list[Document] = Field(default_factory=list)

    @model_validator(mode='after')
    def validate_content_exists(self) -> 'Message':
        if not any([
            self.text is not None and len(self.text.strip()) > 0,
            len(self.images) > 0,
            # len(self.documents) > 0
        ]):
            raise ValueError(
                "Message must contain at least one of: non-empty text, image, or document"
            )
        return self

    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        
        # Handle Role enumeration
        data['role'] = self.role.value
        
        # Handle images
        if self.images:
            data['images'] = [img.model_dump() for img in self.images]
            
        # Handle documents
        if hasattr(self, 'documents') and self.documents:
            data['documents'] = [doc.to_json() for doc in self.documents]
            
        return data

    @classmethod
    def model_validate(cls, obj, **kwargs):
        if isinstance(obj, dict):
            # Handle Role enumeration
            if 'role' in obj:
                obj['role'] = Role(obj['role'])
                
            # Handle images
            if 'images' in obj and obj['images']:
                obj['images'] = [Image.from_json(img_data) for img_data in obj['images']]
                
            # Handle documents
            if 'documents' in obj and obj['documents']:
                obj['documents'] = [Document.from_json(doc_data) for doc_data in obj['documents']]
        
        return super().model_validate(obj, **kwargs)


if __name__ == "__main__":
    import json
    import os
    init()  # Initialize colorama
    
    SUCCESS = f"{Fore.GREEN}✓{Fore.RESET}"
    FAILURE = f"{Fore.RED}✗{Fore.RESET}"
    
    print("\n=== Testing Message Serialization ===")
    
    # 1. Create test message with all types of content
    try:
        # Get image from URL (using the same URL as in Image tests)
        image_url = "https://www.gstatic.com/webp/gallery/1.webp"
        print(f"Downloading image from {image_url}")
        img = Image.from_url(image_url)
        
        # Get document from URL (using the PDF from Document tests)
        doc_url = "https://raw.githubusercontent.com/mozilla/pdf.js/master/examples/learning/helloworld.pdf"
        print(f"Downloading document from {doc_url}")
        doc = Document.from_url(doc_url, encoding='latin1')
        
        # Create message with all content types
        msg = Message(
            text="Test message with all content types",
            images=[img],
            documents=[doc],
            role=Role.ASSISTANT
        )
        
        # Save to JSON
        json_file = "test_message.json"
        print(f"\nSaving message to JSON: {json_file}")
        with open(json_file, 'w') as f:
            json.dump(msg.to_json(), f)
            
        # Load back from JSON
        print(f"Loading message from JSON: {json_file}")
        with open(json_file, 'r') as f:
            loaded_msg = Message.from_json(json.load(f))
            
        # Verify content
        print("\nVerifying loaded message:")
        print(f"Role matches: {msg.role == loaded_msg.role}")
        print(f"Text matches: {msg.text == loaded_msg.text}")
        print(f"Number of images: original={len(msg.images)}, loaded={len(loaded_msg.images)}")
        print(f"Number of documents: original={len(msg.documents)}, loaded={len(loaded_msg.documents)}")
        
        if msg.images and loaded_msg.images:
            print(f"Image dimensions match: {msg.images[0].width}x{msg.images[0].height} vs {loaded_msg.images[0].width}x{loaded_msg.images[0].height}")
            
        if msg.documents and loaded_msg.documents:
            print(f"Document content length matches: {len(msg.documents[0].content)} vs {len(loaded_msg.documents[0].content)}")
        
        # Clean up
        print("\nCleaning up files...")
        try:
            os.remove(json_file)
            print(f"Removed: {json_file}")
        except Exception as e:
            print(f"Error removing {json_file}: {e}")
            
    except Exception as e:
        print(f"Error in serialization test: {str(e)}")
        
    # Test with dummy content
    print("\n=== Testing with Dummy Content ===")
    
    # Create dummy document with unicode content
    content = """Hello, this is a test document!
With multiple lines.
And some unicode characters:
- Japanese: こんにちは
- Chinese: 你好
- Russian: Привет
- Arabic: مرحبا
- Emojis: 🌟 🌍 🚀
"""
    try:
        # Create dummy document
        doc = Document(
            content=content,
            name="test",
            extension="txt",
            encoding='utf-8'
        )
        print(f"{SUCCESS} Created dummy document")
        
        # Create message with dummy document
        msg = Message(documents=[doc])
        print(f"{SUCCESS} Created message with dummy document")
        
        # Save to JSON and load back
        json_file = "test_dummy_message.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(msg.to_json(), f, ensure_ascii=False)
        
        with open(json_file, 'r', encoding='utf-8') as f:
            loaded_msg = Message.from_json(json.load(f))
        
        # Verify content
        content_matches = msg.documents[0].content == loaded_msg.documents[0].content
        print(f"{SUCCESS if content_matches else FAILURE} Document content preserved through serialization")
        os.remove(json_file)
        
    except Exception as e:
        print(f"{FAILURE} Dummy document test failed: {e}")

    # Run the original validation tests
    print("\n=== Running Original Validation Tests ===")
    
    # Test valid cases
    print("\n=== Testing Valid Messages ===")
    
    # Test 1: Text only
    try:
        msg = Message(text="Hello, world!")
        print(f"{SUCCESS} Text only message created successfully. Role: {msg.role}")
    except Exception as e:
        print(f"{FAILURE} Text only message failed: {e}")

    # Test 2: Image only
    try:
        img = Image(
            image=None,  # This should fail
            name="test_image",
            format="jpg"
        )
        msg = Message(images=[img])
        print(f"{FAILURE} Image only message should have failed with None image")
    except ValueError as e:
        print(f"{SUCCESS} Image only message correctly rejected: {e}")

    # Test 3: Document only
    try:
        doc = Document(
            content="Test content",
            name="test_doc",
            extension="txt"
        )
        msg = Message(documents=[doc])
        print(f"{SUCCESS} Document only message created successfully. Role: {msg.role}")
    except Exception as e:
        print(f"{FAILURE} Document only message failed: {e}")

    # Test 4: Combination
    try:
        msg = Message(
            text="Message with everything",
            images=[img],
            documents=[doc],
            role=Role.ASSISTANT
        )
        print(f"{SUCCESS} Combined message created successfully. Role: {msg.role}")
    except Exception as e:
        print(f"{FAILURE} Combined message failed: {e}")

    # Test invalid cases
    print("\n=== Testing Invalid Messages ===")

    # Test 5: Empty message
    try:
        msg = Message()
        print(f"{FAILURE} Empty message should have failed")
    except ValueError as e:
        print(f"{SUCCESS} Empty message correctly rejected: {e}")

    # Test 6: Whitespace-only text
    try:
        msg = Message(text="   ")
        print(f"{FAILURE} Whitespace-only text should have failed")
    except ValueError as e:
        print(f"{SUCCESS} Whitespace-only text correctly rejected: {e}")

    # Test 7: Empty lists
    try:
        msg = Message(images=[], documents=[])
        print(f"{FAILURE} Empty lists should have failed")
    except ValueError as e:
        print(f"{SUCCESS} Empty lists correctly rejected: {e}")
