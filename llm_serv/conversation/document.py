import base64
import os
from typing import Optional, Annotated
from pydantic import BaseModel, Field, GetJsonSchemaHandler, PlainSerializer, PlainValidator
from typing_extensions import Annotated
from colorama import init, Fore

class Document(BaseModel):
    """
    The document class handles the loading, saving, and serialization of documents.
    It can store text or binary data.    
    """

    model_config = {
        "arbitrary_types_allowed": True
    }
        
    _content_base64: str  # base64 encoded string
    _is_binary: bool = False  # this is true if the content is binary
    
    name: Optional[str] = None
    path: Optional[str] = None
    extension: Optional[str] = None  # this is the format, like 'pdf'|'csv'|'doc'|'docx'|'xls'|'xlsx'|'html'|'txt'|'md'
    size: Optional[int] = None
    encoding: str = 'utf-8'
    meta: dict = {}

    @property
    def content(self) -> bytes | str:
        """Returns the content in its original form (bytes or str)"""
        if self._is_binary:
            return base64.b64decode(self._content_base64)
        else:
            return base64.b64decode(self._content_base64).decode(self.encoding)

    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        # Ensure content is properly encoded
        data['_content_base64'] = self._content_base64
        data['_is_binary'] = self._is_binary
        return data

    @classmethod
    def model_validate(cls, obj, **kwargs):
        if isinstance(obj, dict):
            # Ensure content is properly encoded
            if '_content_base64' not in obj:
                content = obj.pop('content', None)
                if content is not None:
                    if isinstance(content, bytes):
                        obj['_is_binary'] = True
                        obj['_content_base64'] = base64.b64encode(content).decode()
                    else:
                        obj['_is_binary'] = False
                        obj['_content_base64'] = base64.b64encode(str(content).encode()).decode()
        return super().model_validate(obj, **kwargs)

    @classmethod
    def load(cls, file_path: str) -> 'Document':
        if not file_path:
            raise ValueError("Empty path provided")
        
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            name = os.path.splitext(os.path.basename(file_path))[0]
            extension = os.path.splitext(file_path)[1].lstrip('.').lower()
            path = os.path.dirname(os.path.abspath(file_path))
            size = os.path.getsize(file_path)
            
            # Try to decode as text
            is_binary = True
            try:
                content.decode('utf-8')
                is_binary = False
            except UnicodeDecodeError:
                pass

            return cls(
                _content_base64=base64.b64encode(content).decode(),
                _is_binary=is_binary,
                path=path,
                name=name,
                extension=extension,
                size=size,
                encoding='utf-8'
            )
        except Exception as e:
            raise IOError(f"Failed to load document from {file_path}: {str(e)}")

    def save(self, path: str) -> None:
        try:
            with open(path, 'wb') as f:
                f.write(self.content)
            self.path = os.path.dirname(os.path.abspath(path))
            self.name = os.path.splitext(os.path.basename(path))[0]
            self.extension = os.path.splitext(path)[1].lstrip('.').lower()
            self.size = len(self.content)
        except Exception as e:
            raise IOError(f"Failed to save document to {path}: {str(e)}")

    @classmethod
    def from_bytes(cls, bytes_data: bytes, encoding: str = 'utf-8') -> 'Document':
        if not bytes_data:
            raise ValueError("Empty bytes input")
            
        # Try to decode as text
        is_binary = True
        try:
            bytes_data.decode('utf-8')
            is_binary = False
        except UnicodeDecodeError:
            pass

        return cls(
            _content_base64=base64.b64encode(bytes_data).decode(),
            _is_binary=is_binary,
            size=len(bytes_data),
            path="",
            name="",
            encoding=encoding
        )

    @classmethod
    def from_url(cls, url: str, encoding: str = 'utf-8') -> 'Document':
        if not url:
            raise ValueError("Empty URL provided")
            
        try:
            import requests
            response = requests.get(url)
            response.raise_for_status()
            
            content = response.content
            # Try to decode as text
            is_binary = True
            try:
                content.decode('utf-8')
                is_binary = False
            except UnicodeDecodeError:
                pass

            return cls(
                _content_base64=base64.b64encode(content).decode(),
                _is_binary=is_binary,
                size=len(content),
                path="",
                name=os.path.splitext(os.path.basename(url))[0],
                extension=os.path.splitext(url)[1].lstrip('.').lower(),
                encoding=encoding
            )
        except requests.RequestException as e:
            raise ValueError(f"Failed to fetch document from URL: {str(e)}")

    
def main():
    import json
    import requests
    from colorama import init, Fore
    init()
    
    SUCCESS = f"{Fore.GREEN}✓{Fore.RESET}"
    FAILURE = f"{Fore.RED}✗{Fore.RESET}"
    
    # Test 1: PDF Document from URL
    print("\n=== Test 1: PDF Document ===")
    pdf_url = "https://raw.githubusercontent.com/mozilla/pdf.js/master/examples/learning/helloworld.pdf"
    print(f"Downloading PDF from {pdf_url}")
    saved_files = []
    
    try:
        # Download and create PDF document
        pdf_doc = Document.from_url(pdf_url, encoding='latin1')
        print(f"{SUCCESS} PDF downloaded and created successfully")
        
        # Save PDF and its JSON representation
        try:
            pdf_doc.save("test_document.pdf")
            saved_files.append("test_document.pdf")
            print(f"{SUCCESS} Saved PDF document")
        except Exception as e:
            print(f"{FAILURE} Failed to save PDF: {e}")
        
        try:
            with open("test_document.pdf.json", 'w') as f:
                json.dump(pdf_doc.model_dump(), f)
            saved_files.append("test_document.pdf.json")
            print(f"{SUCCESS} Saved PDF to JSON")
        except Exception as e:
            print(f"{FAILURE} Failed to save PDF JSON: {e}")
        
        # Load back and compare
        try:
            with open("test_document.pdf.json", 'r') as f:
                loaded_pdf = Document.model_validate(json.load(f))
            print(f"{SUCCESS} Loaded PDF from JSON")
            
            # Verify content
            content_matches = pdf_doc.content == loaded_pdf.content
            size_matches = pdf_doc.size == loaded_pdf.size
            print("\nVerifying PDF document:")
            print(f"{SUCCESS if size_matches else FAILURE} Size matches: {pdf_doc.size} bytes vs {loaded_pdf.size} bytes")
            print(f"{SUCCESS if content_matches else FAILURE} Content matches")
        except Exception as e:
            print(f"{FAILURE} Failed to verify PDF: {e}")
            
    except Exception as e:
        print(f"{FAILURE} PDF test failed: {str(e)}")

    # Test 2: UTF-8 Text Document
    print("\n=== Test 2: UTF-8 Text Document ===")
    content = """Hello, this is a test document!
With multiple lines.
And some unicode characters:
- Japanese: こんにちは
- Chinese: 你好
- Russian: Привет
- Arabic: مرحبا
- Emojis: 🌟 🌍 🚀
""".encode('utf-8')
    
    try:
        # Create text document using the new base64 fields
        text_doc = Document(
            _content_base64=base64.b64encode(content).decode(),
            _is_binary=False,
            name="test",
            extension="txt",
            encoding='utf-8'
        )
        print(f"{SUCCESS} Created text document")
        
        # Save in different formats
        formats = ['txt', 'md', 'log']
        
        for fmt in formats:
            filename = f"test_document.{fmt}"
            try:
                text_doc.save(filename)
                saved_files.append(filename)
                print(f"{SUCCESS} Saved as {filename}")
            except Exception as e:
                print(f"{FAILURE} Failed to save as {filename}: {e}")
        
        # Save as JSON
        json_file = "test_document.json"
        try:
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(text_doc.model_dump(), f, ensure_ascii=False)
            saved_files.append(json_file)
            print(f"{SUCCESS} Saved to JSON: {json_file}")
        except Exception as e:
            print(f"{FAILURE} Failed to save JSON: {e}")
        
        # Load from JSON and verify
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                loaded_doc = Document.model_validate(json.load(f))
            print(f"{SUCCESS} Loaded from JSON")
            
            # Verify content
            content_matches = text_doc.content == loaded_doc.content
            size_matches = text_doc.size == loaded_doc.size
            print("\nVerifying text document:")
            print(f"{SUCCESS if size_matches else FAILURE} Size matches: {text_doc.size} bytes vs {loaded_doc.size} bytes")
            print(f"{SUCCESS if content_matches else FAILURE} Content matches")
            
            # Document properties
            print("\nDocument properties:")
            print(f"{SUCCESS} Name: {loaded_doc.name}")
            print(f"{SUCCESS} Extension: {loaded_doc.extension}")
            print(f"{SUCCESS} Size: {loaded_doc.size} bytes")
            print(f"{SUCCESS} Path: {loaded_doc.path}")
            print(f"{SUCCESS} Encoding: {loaded_doc.encoding}")
        except Exception as e:
            print(f"{FAILURE} Failed to verify text document: {e}")
            
    except Exception as e:
        print(f"{FAILURE} Text document test failed: {str(e)}")
    
    # Clean up
    print("\nCleaning up files...")
    for file in saved_files:
        try:
            os.remove(file)
            print(f"{SUCCESS} Removed: {file}")
        except Exception as e:
            print(f"{FAILURE} Error removing {file}: {e}")


if __name__ == "__main__":
    main()
