import base64
import os
from io import BytesIO
from typing import Optional

import requests
from PIL import Image as PILImage
from pydantic import BaseModel
from colorama import init, Fore


class Image(BaseModel):
    model_config = {
        "arbitrary_types_allowed": True,
        "json_schema_extra": {
            "examples": [{"image": "base64_encoded_image_data"}]
        }
    }
    
    image: PILImage.Image
    name: Optional[str] = None
    path: Optional[str] = None
    exif: dict = {}
    meta: dict = {}

    @property
    def format(self) -> Optional[str]:
        return self.image.format.lower() if self.image and self.image.format else None

    def model_dump(self, **kwargs):        
        return self.to_json()

    def model_dump_json(self, **kwargs):        
        return json.dumps(self.to_json())

    @classmethod
    def model_validate(cls, obj):
        # Handle deserialization of base64 image data
        if isinstance(obj, dict) and 'image' in obj and isinstance(obj['image'], str):
            obj = obj.copy()  # Create a copy to avoid modifying the input
            try:
                obj['image'] = cls.import_from_base64(cls, obj['image'])
            except Exception as e:
                raise ValueError(f"Failed to decode base64 image data: {str(e)}")
        return super().model_validate(obj)

    def set_format(self, new_format: str):
        if not self.image:
            raise ValueError("No image data available to set format")
        
        # Convert image to bytes in the new format
        img_byte_arr = BytesIO()
        self.image.save(img_byte_arr, format=new_format)
        
        # Reload the image from the bytes buffer
        img_byte_arr.seek(0)
        self.image = PILImage.open(img_byte_arr)

    @property
    def width(self) -> int:
        return self.image.width if self.image else None

    @property
    def height(self) -> int:
        return self.image.height if self.image else None

    @staticmethod
    def bytes_to_pil(bytes_data: bytes) -> PILImage.Image:
        return PILImage.open(BytesIO(bytes_data))
    
    @staticmethod
    def _pil_to_bytes(image: PILImage.Image) -> bytes:
        img_byte_arr = BytesIO()
        image.save(img_byte_arr, format=image.format or 'png')
        return img_byte_arr.getvalue()
    
    @staticmethod
    def _get_image_from_url(url: str) -> bytes:
        response = requests.get(url)
        response.raise_for_status()
        return response.content

    def export_as_base64(self, image: PILImage.Image) -> str:
        return base64.b64encode(self._pil_to_bytes(image)).decode()

    def import_from_base64(self, base64_str: str) -> PILImage.Image:
        return self.bytes_to_pil(base64.b64decode(base64_str))

    def to_json(self) -> dict:
        if not self.image:
            raise ValueError("No image data available")
        
        return {
            "image": self.export_as_base64(self.image),
            **self.model_dump(exclude={"image"})
        }
    
    @classmethod
    def from_bytes(cls, bytes_data: bytes) -> 'Image':
        if not bytes_data:
            raise ValueError("Empty bytes input")
            
        img = cls.bytes_to_pil(bytes_data)
        return cls(
            image=img,
            path="",
            name="",
            extension=img.format.lower() if img.format else None
        )

    @classmethod
    def from_url(cls, url: str) -> 'Image':
        if not url:
            raise ValueError("Empty URL provided")
            
        try:
            bytes_data = cls._get_image_from_url(url)
            img = cls.bytes_to_pil(bytes_data)
            
            exif_data = {}
            try:
                exif_data = dict(img._getexif() or {})
            except (AttributeError, TypeError):
                pass
                
            return cls(
                image=img,
                path="",
                name=os.path.splitext(os.path.basename(url))[0],
                extension=img.format.lower() if img.format else None,
                exif=exif_data
            )
        except requests.RequestException as e:
            raise ValueError(f"Failed to fetch image from URL: {str(e)}")

    @classmethod
    def from_json(cls, json_data: dict) -> 'Image':
        if not json_data or 'image' not in json_data:
            raise ValueError("Invalid JSON data: missing 'image' field")
            
        try:
            image_data = json_data.pop('image')  # Remove image field to avoid duplicate processing
            img = cls.import_from_base64(cls, image_data)
            return cls(image=img, **json_data)
        except Exception as e:
            raise ValueError(f"Failed to parse JSON data: {str(e)}")

    def save(self, path: str):        
        self.image.save(path)

    
    @staticmethod
    def load(path: str) -> 'Image':
        if not path:
            raise ValueError("Empty path provided")
            
        try:
            img = PILImage.open(path)
            image = Image(
                image=img,
                path=path,
                format=img.format.lower() if img.format else None
            )
            
            try:
                image.exif = dict(img._getexif() or {})
            except Exception:
                image.exif = {}
                
            # Extract file name without extension
            image.name = os.path.splitext(os.path.basename(path))[0]
            
            return image
        except Exception as e:
            raise IOError(f"Failed to load image from {path}: {str(e)}")


if __name__ == "__main__":
    import json
    import os
    from colorama import init, Fore
    init()
    
    SUCCESS = f"{Fore.GREEN}✓{Fore.RESET}"
    FAILURE = f"{Fore.RED}✗{Fore.RESET}"

    # 1. Download and create image
    try:
        url = "https://www.gstatic.com/webp/gallery/1.webp"
        print(f"\n=== Test 1: Image Download and Creation ===")
        print(f"Downloading image from {url}")
        img = Image.from_url(url)
        print(f"{SUCCESS} Image downloaded and created successfully")
        
        # 2. Print properties
        print("\nImage properties:")
        print(f"{SUCCESS} Name: {img.name}")
        print(f"{SUCCESS} Extension: {img.format}")
        print(f"{SUCCESS} Dimensions: {img.width}x{img.height}")
        print(f"{SUCCESS} Path: {img.path}")
        print(f"{SUCCESS} EXIF data entries: {len(img.exif)}")
        
        # 3. Save in different formats
        print("\n=== Test 2: Format Conversion ===")
        formats = ['webp', 'jpg', 'png']
        saved_files = []
        
        for fmt in formats:
            filename = f"test_image.{fmt}"
            try:
                img.save(filename)
                saved_files.append(filename)
                print(f"{SUCCESS} Saved as {filename}")
            except Exception as e:
                print(f"{FAILURE} Failed to save as {filename}: {e}")
        
        # 4. Save as JSON
        print("\n=== Test 3: JSON Serialization ===")
        json_file = "test_image.json"
        try:
            with open(json_file, 'w') as f:
                json.dump(img.to_json(), f)
            saved_files.append(json_file)
            print(f"{SUCCESS} Saved to JSON: {json_file}")
            
            # 5. Load from JSON
            with open(json_file, 'r') as f:
                loaded_img = Image.from_json(json.load(f))
            print(f"{SUCCESS} Loaded from JSON successfully")
            
            # 6. Verify loaded image
            print("\nVerifying loaded image:")
            dimensions_match = img.width == loaded_img.width and img.height == loaded_img.height
            print(f"{SUCCESS if dimensions_match else FAILURE} Dimensions match: {img.width}x{img.height} vs {loaded_img.width}x{loaded_img.height}")
            
        except Exception as e:
            print(f"{FAILURE} JSON serialization test failed: {e}")
        
        # 7. Clean up
        print("\n=== Cleanup ===")
        for file in saved_files:
            try:
                os.remove(file)
                print(f"{SUCCESS} Removed: {file}")
            except Exception as e:
                print(f"{FAILURE} Error removing {file}: {e}")
                
    except Exception as e:
        print(f"{FAILURE} Main test failed: {e}")
