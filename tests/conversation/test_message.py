import json
import pytest
from pathlib import Path

from llm_serv.conversation.message import Message
from llm_serv.conversation.role import Role
from llm_serv.conversation.image import Image
from llm_serv.conversation.document import Document

@pytest.fixture
def sample_text():
    return "Hello, this is a test message with unicode: 你好 こんにちは 🌟"

@pytest.fixture
def sample_image_url():
    return "https://www.gstatic.com/webp/gallery/1.webp"

@pytest.fixture
def test_image(sample_image_url):
    return Image.from_url(sample_image_url)

@pytest.fixture
def test_document():
    content = """Hello, this is a test document!
With multiple lines.
And some unicode characters:
- Japanese: こんにちは
- Chinese: 你好
- Emojis: 🌟 🌍 🚀
"""
    return Document(
        content=content,
        name="test_doc",
        extension="txt",
        encoding='utf-8'
    )

@pytest.fixture
def test_message(sample_text, test_image, test_document):
    return Message(
        text=sample_text,
        images=[test_image],
        documents=[test_document],
        role=Role.ASSISTANT
    )

def test_message_creation_basic():
    """Test basic message creation with different content types"""
    # Text only
    msg = Message(text="Hello world")
    assert msg.text == "Hello world"
    assert msg.role == Role.USER  # Default role
    
    # Role specification
    msg = Message(text="Hello", role=Role.ASSISTANT)
    assert msg.role == Role.ASSISTANT
    
    # Empty lists should be created
    assert isinstance(msg.images, list)
    assert len(msg.images) == 0

def test_message_validation():
    """Test message validation rules"""
    # Empty message should fail
    with pytest.raises(ValueError):
        Message()
    
    # Whitespace-only text should fail
    with pytest.raises(ValueError):
        Message(text="   ")
    
    # Empty lists with no text should fail
    with pytest.raises(ValueError):
        Message(images=[], documents=[])
    
    # Valid combinations should pass
    Message(text="Valid")  # Text only
    Message(images=[Image.from_url("https://www.gstatic.com/webp/gallery/1.webp")])  # Image only
    Message(documents=[Document(content="test", name="test", extension="txt")])  # Document only

def test_message_with_image(test_image):
    """Test message creation and handling with images"""
    # Single image
    msg = Message(images=[test_image])
    assert len(msg.images) == 1
    assert msg.images[0].width > 0
    assert msg.images[0].height > 0
    
    # Multiple images
    msg = Message(images=[test_image, test_image])
    assert len(msg.images) == 2

def test_message_with_document(test_document):
    """Test message creation and handling with documents"""
    # Single document
    msg = Message(documents=[test_document])
    assert len(msg.documents) == 1
    assert msg.documents[0].content == test_document.content
    assert msg.documents[0].encoding == 'utf-8'
    
    # Multiple documents
    msg = Message(documents=[test_document, test_document])
    assert len(msg.documents) == 2

def test_message_json_serialization(test_message):
    """Test complete message serialization to and from JSON"""
    # Convert to JSON
    json_data = test_message.model_dump()
    
    # Verify JSON structure
    assert 'text' in json_data
    assert 'role' in json_data
    assert 'images' in json_data
    assert 'documents' in json_data
    assert isinstance(json_data['images'], list)
    assert isinstance(json_data['documents'], list)
    
    # Convert back from JSON
    loaded_message = Message.model_validate(json_data)
    
    # Verify all properties match
    assert loaded_message.text == test_message.text
    assert loaded_message.role == test_message.role
    assert len(loaded_message.images) == len(test_message.images)
    assert len(loaded_message.documents) == len(test_message.documents)
    
    # Verify image properties
    assert loaded_message.images[0].width == test_message.images[0].width
    assert loaded_message.images[0].height == test_message.images[0].height
    
    # Verify document properties
    assert loaded_message.documents[0].content == test_message.documents[0].content
    assert loaded_message.documents[0].encoding == test_message.documents[0].encoding

def test_message_file_serialization(test_message, tmp_path):
    """Test saving and loading message to/from file"""
    json_file = tmp_path / "test_message.json"
    
    # Save to file
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(test_message.model_dump(), f, ensure_ascii=False)
    
    # Load from file
    with open(json_file, 'r', encoding='utf-8') as f:
        loaded_data = json.load(f)
    loaded_message = Message.model_validate(loaded_data)
    
    # Verify content
    assert loaded_message.text == test_message.text
    assert loaded_message.role == test_message.role
    assert len(loaded_message.images) == len(test_message.images)
    assert len(loaded_message.documents) == len(test_message.documents)

def test_message_edge_cases():
    """Test edge cases and potential error conditions"""
    # Very long text
    long_text = "a" * 999900
    msg = Message(text=long_text)
    assert len(msg.text) == 999900
    
    # Unicode edge cases
    unicode_text = "🌟" * 1000
    msg = Message(text=unicode_text)
    assert len(msg.text) == 1000
    
    # Many images
    many_images = [Image.from_url("https://www.gstatic.com/webp/gallery/1.webp")] * 10
    msg = Message(images=many_images)
    assert len(msg.images) == 10
    
    # Invalid role
    with pytest.raises(ValueError):
        Message(text="test", role="INVALID_ROLE")

def test_message_model_validation():
    """Test model validation with various input formats"""
    # Dict input
    data = {
        "text": "Hello",
        "role": "USER",
        "images": [],
        "documents": []
    }
    msg = Message.model_validate(data)
    assert msg.text == "Hello"
    assert msg.role == Role.USER
    
    # Invalid dict input
    with pytest.raises(ValueError):
        Message.model_validate({"role": "INVALID"})
    
    # None input
    with pytest.raises(ValueError):
        Message.model_validate(None)
    
    # Empty dict
    with pytest.raises(ValueError):
        Message.model_validate({})

def test_message_role_handling():
    """Test role handling and validation"""
    # Test all valid roles
    for role in Role:
        msg = Message(text="test", role=role)
        assert msg.role == role
        
        # Test serialization preserves role
        json_data = msg.model_dump()
        loaded_msg = Message.model_validate(json_data)
        assert loaded_msg.role == role
    
    # Test role string conversion
    msg = Message(text="test", role="ASSISTANT")
    assert msg.role == Role.ASSISTANT
    
    # Test invalid role string
    with pytest.raises(ValueError):
        Message(text="test", role="INVALID") 