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
        exclude = kwargs.pop('exclude', set())
        if 'image' not in exclude:
            # Convert image to base64 when dumping
            result = {
                "image": self.export_as_base64(self.image),
                **super().model_dump(exclude={"image"}, **kwargs)
            }
        else:
            result = super().model_dump(**kwargs)
        return result

    @classmethod
    def model_validate(cls, obj, **kwargs):
        if isinstance(obj, str):
            # Handle file path input
            return cls.load(obj)
        elif isinstance(obj, dict):
            if 'image' in obj and isinstance(obj['image'], str):
                # Check if it's a file path or base64
                if os.path.exists(obj['image']):
                    img = cls.load(obj['image'])
                    # Merge any additional fields from obj
                    return cls(**{**obj, 'image': img.image})
                else:
                    # Assume base64
                    try:
                        obj = obj.copy()
                        obj['image'] = cls.import_from_base64(cls, obj['image'])
                    except Exception as e:
                        raise ValueError(f"Failed to decode base64 image data: {str(e)}")
        return super().model_validate(obj, **kwargs)

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
