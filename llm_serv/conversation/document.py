import base64
import os
from typing import Optional
from pydantic import BaseModel, Field
from colorama import init, Fore


class Document(BaseModel):
    model_config = {
        "arbitrary_types_allowed": True
    }
    
    content: bytes
    
    name: Optional[str] = None
    path: Optional[str] = None
    extension: Optional[str] = None  # this is the format, like 'pdf'|'csv'|'doc'|'docx'|'xls'|'xlsx'|'html'|'txt'|'md'
    size: Optional[int] = None
    encoding: str = 'utf-8'
    
    meta: dict = {}

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
            encoding = 'utf-8' # to do: detect encoding

            return cls(
                content=content,
                path=path,
                name=name,
                extension=extension,
                size=size,
                encoding=encoding
            )        
        except Exception as e:
            raise IOError(f"Failed to load document from {file_path}: {str(e)}")


    def to_json(self) -> dict:
        if not self.content:
            raise ValueError("No document content available")
        
        return {
            "content": base64.b64encode(self.content).decode(),
            **self.model_dump(exclude={"content"})
        }
    
    @classmethod
    def from_bytes(cls, bytes_data: bytes, encoding: str = 'utf-8') -> 'Document': # TODO not ok, no name, no path, no extension
        if not bytes_data:
            raise ValueError("Empty bytes input")
            
        return cls(
            content=bytes_data,
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
            
            return cls(
                content=response.content,
                size=len(response.content),
                path="",
                name=os.path.splitext(os.path.basename(url))[0],
                extension=os.path.splitext(url)[1].lstrip('.').lower(),
                encoding=encoding
            )
        except requests.RequestException as e:
            raise ValueError(f"Failed to fetch document from URL: {str(e)}")

    @classmethod
    def from_json(cls, json_data: dict) -> 'Document':
        if not json_data or 'content' not in json_data:
            raise ValueError("Invalid JSON data: missing 'content' field")
            
        try:
            content_data = json_data.pop('content')
            content = base64.b64decode(content_data)
            return cls(content=content, **json_data)
        except Exception as e:
            raise ValueError(f"Failed to parse JSON data: {str(e)}")

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
    def load(cls, path: str, encoding: str = 'utf-8') -> 'Document':
        if not path:
            raise ValueError("Empty path provided")
            
        try:
            with open(path, 'rb') as f:
                content = f.read()
            
            return cls(
                content=content,
                path=os.path.dirname(os.path.abspath(path)),
                name=os.path.splitext(os.path.basename(path))[0],
                extension=os.path.splitext(path)[1].lstrip('.').lower(),
                size=os.path.getsize(path),
                encoding=encoding
            )
        except Exception as e:
            raise IOError(f"Failed to load document from {path}: {str(e)}")


def main():
    import json
    import requests
    from colorama import init, Fore
    init()
    
    SUCCESS = f"{Fore.GREEN}✓{Fore.RESET}"
    FAILURE = f"{Fore.RED}✗{Fore.RESET}"
    
    # Test 1: PDF Document from URL
    print("\n=== Test 1: PDF Document ===")
    # Using a small, reliable PDF from Mozilla's PDF.js examples
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
                json.dump(pdf_doc.to_json(), f)
            saved_files.append("test_document.pdf.json")
            print(f"{SUCCESS} Saved PDF to JSON")
        except Exception as e:
            print(f"{FAILURE} Failed to save PDF JSON: {e}")
        
        # Load back and compare
        try:
            with open("test_document.pdf.json", 'r') as f:
                loaded_pdf = Document.from_json(json.load(f))
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
"""
    
    try:
        # Create text document
        text_doc = Document(
            content=content,
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
                json.dump(text_doc.to_json(), f, ensure_ascii=False)
            saved_files.append(json_file)
            print(f"{SUCCESS} Saved to JSON: {json_file}")
        except Exception as e:
            print(f"{FAILURE} Failed to save JSON: {e}")
        
        # Load from JSON and verify
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                loaded_doc = Document.from_json(json.load(f))
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
