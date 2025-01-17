import json
import os
import pytest
from colorama import Fore
import requests
from pathlib import Path

from llm_serv.conversation.image import Image



SUCCESS = f"{Fore.GREEN}✓{Fore.RESET}"
FAILURE = f"{Fore.RED}✗{Fore.RESET}"

@pytest.fixture
def sample_image_url():
    return "https://www.gstatic.com/webp/gallery/1.webp"

@pytest.fixture
def large_image_url():
    return "https://www.gstatic.com/webp/gallery/5.webp"

@pytest.fixture
def tiny_image_url():
    return "https://picsum.photos/50/50"

@pytest.fixture
def format_urls():
    return {
        "jpg": "https://www.gstatic.com/webp/gallery/1.jpg",
        "png": "https://www.gstatic.com/webp/gallery/2.png",
        "webp": "https://www.gstatic.com/webp/gallery/3.webp"
    }

@pytest.fixture(scope="session")
def test_images_dir():
    """Create and clean up a temporary directory for test images"""
    test_dir = Path("test_images")
    test_dir.mkdir(exist_ok=True)
    yield test_dir
    # Cleanup all files in directory after tests
    for file in test_dir.glob("*"):
        try:
            file.unlink()
        except Exception:
            pass
    test_dir.rmdir()

@pytest.fixture
def download_image(test_images_dir):
    """Fixture to download and cleanup test images"""
    downloaded_files = []
    
    def _download(url):
        if not url:
            raise ValueError("URL cannot be empty")
            
        local_path = test_images_dir / f"test_image_{len(downloaded_files)}{Path(url).suffix}"
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        downloaded_files.append(local_path)
        return local_path
    
    yield _download
    
    # Cleanup downloaded files
    for file in downloaded_files:
        try:
            file.unlink()
        except Exception:
            pass

@pytest.fixture
def test_image(download_image, sample_image_url):
    local_path = download_image(sample_image_url)
    return Image.model_validate(str(local_path))

def test_image_download_and_creation(test_image):
    assert test_image.name is not None
    assert test_image.format is not None
    assert test_image.width > 0
    assert test_image.height > 0
    assert test_image.path is not None
    assert len(test_image.exif) >= 0

def test_image_format_conversion(test_image, test_images_dir):
    formats = ['webp', 'jpg', 'png']
    
    for fmt in formats:
        filename = test_images_dir / f"test_image.{fmt}"
        test_image.save(filename)
        assert filename.exists()

def test_image_json_serialization(test_image, test_images_dir):
    json_file = test_images_dir / "test_image.json"
    
    # Test model_dump
    json_data = test_image.model_dump()
    assert 'image' in json_data
    assert isinstance(json_data['image'], str)  # Base64 encoded string
    
    # Save to file
    with open(json_file, 'w') as f:
        json.dump(json_data, f)
    
    # Load and validate
    with open(json_file, 'r') as f:
        loaded_data = json.load(f)
    loaded_image = Image.model_validate(loaded_data)
    
    # Verify properties
    assert loaded_image.width == test_image.width
    assert loaded_image.height == test_image.height
    assert loaded_image.format == test_image.format

def test_image_edge_cases(download_image, large_image_url, tiny_image_url, format_urls):
    # Test with large image
    local_path = download_image(large_image_url)
    img = Image.model_validate(str(local_path))
    assert img.width > 800
    assert img.height > 600
    
    # Test with tiny image
    local_path = download_image(tiny_image_url)
    img = Image.model_validate(str(local_path))
    assert img.width < 100
    assert img.height < 100
    
    # Test with various image formats
    for fmt, url in format_urls.items():
        local_path = download_image(url)
        img = Image.model_validate(str(local_path))
        assert img.format.lower() in [fmt, "jpeg"]  # handle jpg/jpeg case

def test_image_invalid_cases():
    with pytest.raises(Exception):
        Image.model_validate("nonexistent_file.jpg")
    
    with pytest.raises(ValueError):
        Image.model_validate("")
    
    with pytest.raises(Exception):
        Image.model_validate({"image": "invalid_base64_data"})

def test_image_exif_handling(download_image):
    # Test image with EXIF data
    img_url = "https://raw.githubusercontent.com/ianare/exif-samples/master/jpg/Canon_40D.jpg"
    local_path = download_image(img_url)
    img = Image.model_validate(str(local_path))
    assert len(img.exif) > 0
    
    # Verify EXIF data preservation in JSON
    json_data = img.model_dump()
    loaded_img = Image.model_validate(json_data)
    assert len(loaded_img.exif) == len(img.exif) 