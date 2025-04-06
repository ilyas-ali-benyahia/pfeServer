import re
from langchain.document_loaders import UnstructuredFileLoader
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import pytesseract
from PIL import Image

def txt_to_text(txt_path):
    """
    Read text from a plain text file.
    
    Args:
        txt_path (str): Path to the text file
        
    Returns:
        str: Content of the text file
    """
    try:
        with open(txt_path, 'r', encoding='utf-8') as file:
            return file.read()
    except UnicodeDecodeError:
        # Try different encodings if UTF-8 fails
        try:
            with open(txt_path, 'r', encoding='latin-1') as file:
                return file.read()
        except Exception as e:
            raise Exception(f"Failed to read text file: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to read text file: {str(e)}")

# Function to extract text from images using OCR
def image_to_text(image_path):
    """
    Extract text from an image using Tesseract OCR.
    
    Args:
        image_path (str): Path to the image file
        
    Returns:
        str: Extracted text from the image
    """
    try:
        # Open the image using PIL
        img = Image.open(image_path)
        
        # Use pytesseract to do OCR on the image
        text = pytesseract.image_to_string(img)
        
        return text
    except Exception as e:
        raise Exception(f"OCR processing failed: {str(e)}")



def pptx_to_text(pptx_path):
    """Extract text from PowerPoint files"""
    # Using UnstructuredFileLoader
    loader = UnstructuredFileLoader(pptx_path)
    documents = loader.load()
    text = "\n\n".join([doc.page_content for doc in documents])
    
    return text

def docx_to_text(docx_path):
    """Extract text from Word documents"""
    # Using UnstructuredFileLoader
    loader = UnstructuredFileLoader(docx_path)
    documents = loader.load()
    text = "\n\n".join([doc.page_content for doc in documents])
    
    return text