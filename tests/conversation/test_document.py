import os
import json
import pytest
import tempfile
import requests
from pathlib import Path
from llm_serv.conversation.document import Document


@pytest.fixture
def sample_text_content():
    return """Hello, this is a test document!
With multiple lines.
And some unicode characters:
- Japanese: こんにちは
- Chinese: 你好
- Russian: Привет
- Arabic: مرحبا
- Emojis: 🌟 🌍 🚀
""".encode('utf-8')

@pytest.fixture
def sample_pdf_url():
    return "https://raw.githubusercontent.com/mozilla/pdf.js/master/examples/learning/helloworld.pdf"

@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield Path(tmpdirname)

def test_create_document_from_text(sample_text_content):
    doc = Document(
        content=sample_text_content,
        name="test",
        extension="txt",
        encoding='utf-8'
    )
    assert doc.content == sample_text_content
    assert doc.name == "test"
    assert doc.extension == "txt"
    assert doc.encoding == "utf-8"
    assert doc.size is None  # Size is only set when loading from file or saving
    assert doc.path is None
    assert doc.meta == {}

def test_create_document_from_bytes():
    content = b"Simple byte content"
    doc = Document.from_bytes(content)
    assert doc.content == content
    assert doc.size == len(content)
    assert doc.path == ""
    assert doc.name == ""
    assert doc.encoding == "utf-8"

def test_create_document_from_empty_bytes():
    with pytest.raises(ValueError, match="Empty bytes input"):
        Document.from_bytes(b"")

def test_document_save_and_load(temp_dir, sample_text_content):
    # Create and save document
    doc = Document(content=sample_text_content, name="test", extension="txt")
    file_path = temp_dir / "test_doc.txt"
    doc.save(str(file_path))
    
    # Verify file exists and content matches
    assert file_path.exists()
    assert file_path.read_bytes() == sample_text_content
    
    # Load document back
    loaded_doc = Document.load(str(file_path))
    assert loaded_doc.content == sample_text_content
    assert loaded_doc.name == "test_doc"
    assert loaded_doc.extension == "txt"
    assert loaded_doc.size == len(sample_text_content)
    assert loaded_doc.path == str(temp_dir)

def test_document_load_nonexistent_file():
    with pytest.raises(IOError):
        Document.load("nonexistent_file.txt")

def test_document_load_empty_path():
    with pytest.raises(ValueError, match="Empty path provided"):
        Document.load("")

def test_document_json_serialization(sample_text_content):
    # Create document
    doc = Document(
        content=sample_text_content,
        name="test",
        extension="txt",
        encoding='utf-8',
        meta={"key": "value"}
    )
    
    # Serialize to JSON
    json_data = doc.model_dump()
    assert isinstance(json_data["content"], str)  # Content should be base64 encoded
    
    # Deserialize back
    loaded_doc = Document.model_validate(json_data)
    assert loaded_doc.content == sample_text_content
    assert loaded_doc.name == doc.name
    assert loaded_doc.extension == doc.extension
    assert loaded_doc.encoding == doc.encoding
    assert loaded_doc.meta == doc.meta

@pytest.mark.online  # Mark test as requiring internet connection
def test_document_from_url(sample_pdf_url):
    doc = Document.from_url(sample_pdf_url)
    assert doc.content is not None
    assert len(doc.content) > 0
    assert doc.name == "helloworld"
    assert doc.extension == "pdf"
    assert doc.size == len(doc.content)

@pytest.mark.online
def test_document_from_invalid_url():
    with pytest.raises(ValueError):
        Document.from_url("https://nonexistent.example.com/doc.pdf")

def test_document_from_empty_url():
    with pytest.raises(ValueError, match="Empty URL provided"):
        Document.from_url("")

def test_document_save_multiple_formats(temp_dir, sample_text_content):
    doc = Document(content=sample_text_content, name="test")
    formats = ['txt', 'md', 'log']
    
    for fmt in formats:
        file_path = temp_dir / f"test.{fmt}"
        doc.save(str(file_path))
        assert file_path.exists()
        assert file_path.read_bytes() == sample_text_content
        assert doc.extension == fmt

def test_document_with_binary_content(temp_dir):
    # Create some binary content
    binary_content = bytes([x % 256 for x in range(1000)])
    
    # Create and save document
    doc = Document(content=binary_content, name="binary", extension="bin")
    file_path = temp_dir / "test.bin"
    doc.save(str(file_path))
    
    # Load and verify
    loaded_doc = Document.load(str(file_path))
    assert loaded_doc.content == binary_content
    assert loaded_doc.size == len(binary_content)

def test_document_with_large_content(temp_dir):
    # Create a relatively large content (5MB)
    large_content = b"Large content\n" * (5 * 1024 * 1024 // 13)
    
    # Create and save document
    doc = Document(content=large_content, name="large", extension="txt")
    file_path = temp_dir / "large.txt"
    doc.save(str(file_path))
    
    # Load and verify
    loaded_doc = Document.load(str(file_path))
    assert loaded_doc.content == large_content
    assert loaded_doc.size == len(large_content)

def test_document_meta_handling():
    # Test with various meta data types
    meta = {
        "int": 42,
        "float": 3.14,
        "str": "test",
        "list": [1, 2, 3],
        "dict": {"nested": "value"},
        "bool": True,
        "none": None
    }
    
    doc = Document(
        content=b"content",
        name="test",
        meta=meta
    )
    
    # Serialize and deserialize
    json_data = doc.model_dump()
    loaded_doc = Document.model_validate(json_data)
    
    assert loaded_doc.meta == meta

def test_document_path_handling(temp_dir):
    # Test relative path
    rel_path = "subfolder/test.txt"
    full_path = temp_dir / rel_path
    os.makedirs(full_path.parent, exist_ok=True)
    
    doc = Document(content=b"content", name="test")
    doc.save(str(full_path))
    
    assert doc.path == str(full_path.parent)
    assert doc.name == "test"
    
    # Test absolute path
    abs_path = str(full_path.absolute())
    loaded_doc = Document.load(abs_path)
    
    assert loaded_doc.path == str(full_path.parent)
    assert loaded_doc.name == "test" 