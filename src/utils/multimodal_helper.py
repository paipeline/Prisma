from markitdown import MarkItDown
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import os
import json
from pathlib import Path

from ..config.configuration import Configuration
from .llm_helper import vision_llm


@dataclass
class GAIAEntry:
    """
    GAIA dataset entry schema representing a single task/question.
    
    Based on the GAIA dataset structure from huggingface datasets.
    """
    task_id: str
    question: str
    level: int
    final_answer: str
    file_name: str
    file_path: str
    annotator_metadata: Dict[str, str]
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GAIAEntry':
        """Create GAIAEntry from dictionary (e.g., from JSON)."""
        return cls(
            task_id=data.get("task_id", ""),
            question=data.get("Question", ""),
            level=data.get("Level", 1),
            final_answer=data.get("Final answer", "?"),
            file_name=data.get("file_name", ""),
            file_path=data.get("file_path", ""),
            annotator_metadata=data.get("Annotator Metadata", {})
        )


@dataclass
class GAIATaskEntry:
    """
    GAIA task entry WITHOUT answers for blind processing.
    This version excludes the final answer and annotator metadata to prevent cheating.
    """
    task_id: str
    question: str
    level: int
    file_name: str
    file_path: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GAIATaskEntry':
        """Create GAIATaskEntry from dictionary without answer data."""
        return cls(
            task_id=data.get("task_id", ""),
            question=data.get("Question", ""),
            level=data.get("Level", 1),
            file_name=data.get("file_name", ""),
            file_path=data.get("file_path", "")
        )
    
    @classmethod
    def from_gaia_entry(cls, gaia_entry: 'GAIAEntry') -> 'GAIATaskEntry':
        """Convert a full GAIAEntry to a blind GAIATaskEntry."""
        return cls(
            task_id=gaia_entry.task_id,
            question=gaia_entry.question,
            level=gaia_entry.level,
            file_name=gaia_entry.file_name,
            file_path=gaia_entry.file_path
        )


@dataclass
class GAIAProcessedEntry:
    """
    Processed GAIA entry with converted file content.
    """
    gaia_entry: GAIAEntry
    processed_content: str
    content_type: str  # 'text', 'image', 'audio', 'document', 'multimodal'
    processing_method: str  # 'markitdown', 'vision_model', 'audio_transcription', etc.


@dataclass  
class GAIAProcessedTask:
    """
    Processed GAIA task entry WITHOUT answers for blind processing.
    """
    task_entry: GAIATaskEntry
    processed_content: str
    content_type: str
    processing_method: str
    
    
def get_file_type_category(file_path: str) -> str:
    """
    Categorize file type for processing strategy.
    
    Returns:
        'image': Image files that need vision model processing
        'audio': Audio files that need transcription
        'document': Document files that can be processed by markitdown
        'text': Plain text files
        'unsupported': Files that cannot be processed
    """
    if not file_path:
        return 'text'
        
    extension = Path(file_path).suffix.lower()
    
    # Image files - use vision model
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    if extension in image_extensions:
        return 'image'
    
    # Audio files - use audio transcription via markitdown
    audio_extensions = {'.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg'}
    if extension in audio_extensions:
        return 'audio'
    
    # Document files - use markitdown
    document_extensions = {'.pdf', '.docx', '.pptx', '.xlsx', '.csv', '.json', '.xml', '.html', '.zip', '.epub'}
    if extension in document_extensions:
        return 'document'
    
    # Text files
    text_extensions = {'.txt', '.md', '.py', '.jsonl'}
    if extension in text_extensions:
        return 'text'
    
    # Video files - not directly supported but mention for completeness
    video_extensions = {'.mov', '.mp4', '.avi', '.mkv'}
    if extension in video_extensions:
        return 'unsupported'
    
    # Other/unknown
    return 'unsupported'


def markdown_convert(file_path: str) -> str:
    """
    Support markdown file conversion using markitdown.
    PDF, PowerPoint, Word, Excel, Images (EXIF metadata and OCR), Audio (EXIF metadata and speech transcription), HTML, Text-based formats (CSV, JSON, XML), ZIP files (iterates over contents), Youtube URLs, EPubs
    """
    if not os.path.exists(file_path):
        return f"Error: File not found: {file_path}"
    
    try:
        md = MarkItDown()
        result = md.convert(file_path)
        return result.text_content
    except Exception as e:
        return f"Error converting file {file_path}: {str(e)}"


def vision_model_process(file_path: str, question: str = "") -> str:
    """
    Process image files using vision model with optional question context.
    
    Args:
        file_path: Path to the image file
        question: Optional question context to guide the vision model
        
    Returns:
        Description of the image content
    """
    if not os.path.exists(file_path):
        return f"Error: Image file not found: {file_path}"
    
    try:
        # Create a prompt for the vision model
        if question:
            prompt = f"""Analyze this image in the context of the following question: {question}

Please provide a detailed description of the image that would be helpful for answering the question. Include:
1. Key objects, people, text, or elements visible
2. Spatial relationships and layout
3. Any text that can be read in the image
4. Colors, shapes, and visual patterns
5. Any other relevant details that might help answer the question"""
        else:
            prompt = """Analyze this image and provide a detailed description including:
1. Key objects, people, text, or elements visible
2. Spatial relationships and layout  
3. Any text that can be read in the image
4. Colors, shapes, and visual patterns
5. Any other relevant visual information"""
        
        # Use vision model to analyze the image
        response = vision_llm.invoke([
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"file://{os.path.abspath(file_path)}"}}
        ])
        
        return response.content
        
    except Exception as e:
        return f"Error processing image {file_path} with vision model: {str(e)}"


def process_gaia_file(gaia_entry: GAIAEntry) -> GAIAProcessedEntry:
    """
    Process a GAIA entry file using appropriate method based on file type.
    
    Args:
        gaia_entry: The GAIA entry containing file information
        
    Returns:
        GAIAProcessedEntry with processed content
    """
    if not gaia_entry.file_name:
        # No file attached, just return the question
        return GAIAProcessedEntry(
            gaia_entry=gaia_entry,
            processed_content=gaia_entry.question,
            content_type='text',
            processing_method='direct'
        )
    
    file_type = get_file_type_category(gaia_entry.file_path)
    
    if file_type == 'image':
        # Use vision model for images
        processed_content = vision_model_process(gaia_entry.file_path, gaia_entry.question)
        return GAIAProcessedEntry(
            gaia_entry=gaia_entry,
            processed_content=f"**Question:** {gaia_entry.question}\n\n**Image Analysis:**\n{processed_content}",
            content_type='image',
            processing_method='vision_model'
        )
    
    elif file_type in ['audio', 'document']:
        # Use markitdown for audio and document files
        processed_content = markdown_convert(gaia_entry.file_path)
        return GAIAProcessedEntry(
            gaia_entry=gaia_entry,
            processed_content=f"**Question:** {gaia_entry.question}\n\n**File Content:**\n{processed_content}",
            content_type=file_type,
            processing_method='markitdown'
        )
    
    elif file_type == 'text':
        # Read text files directly
        try:
            with open(gaia_entry.file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            processed_content = f"**Question:** {gaia_entry.question}\n\n**File Content:**\n{file_content}"
        except Exception as e:
            processed_content = f"**Question:** {gaia_entry.question}\n\n**Error reading file:** {str(e)}"
        
        return GAIAProcessedEntry(
            gaia_entry=gaia_entry,
            processed_content=processed_content,
            content_type='text',
            processing_method='direct_read'
        )
    
    else:
        # Unsupported file type
        return GAIAProcessedEntry(
            gaia_entry=gaia_entry,
            processed_content=f"**Question:** {gaia_entry.question}\n\n**Note:** Attached file '{gaia_entry.file_name}' has unsupported format and cannot be processed.",
            content_type='unsupported',
            processing_method='none'
        )


def process_gaia_task_blind(task_entry: GAIATaskEntry) -> GAIAProcessedTask:
    """
    Process a GAIA task WITHOUT access to answers - for blind evaluation.
    
    Args:
        task_entry: The GAIA task entry (without answers)
        
    Returns:
        GAIAProcessedTask with processed content
    """
    if not task_entry.file_name:
        # No file attached, just return the question
        return GAIAProcessedTask(
            task_entry=task_entry,
            processed_content=task_entry.question,
            content_type='text',
            processing_method='direct'
        )
    
    file_type = get_file_type_category(task_entry.file_path)
    
    if file_type == 'image':
        # Use vision model for images
        processed_content = vision_model_process(task_entry.file_path, task_entry.question)
        return GAIAProcessedTask(
            task_entry=task_entry,
            processed_content=f"**Question:** {task_entry.question}\n\n**Image Analysis:**\n{processed_content}",
            content_type='image',
            processing_method='vision_model'
        )
    
    elif file_type in ['audio', 'document']:
        # Use markitdown for audio and document files
        processed_content = markdown_convert(task_entry.file_path)
        return GAIAProcessedTask(
            task_entry=task_entry,
            processed_content=f"**Question:** {task_entry.question}\n\n**File Content:**\n{processed_content}",
            content_type=file_type,
            processing_method='markitdown'
        )
    
    elif file_type == 'text':
        # Read text files directly
        try:
            with open(task_entry.file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            processed_content = f"**Question:** {task_entry.question}\n\n**File Content:**\n{file_content}"
        except Exception as e:
            processed_content = f"**Question:** {task_entry.question}\n\n**Error reading file:** {str(e)}"
        
        return GAIAProcessedTask(
            task_entry=task_entry,
            processed_content=processed_content,
            content_type='text',
            processing_method='direct_read'
        )
    
    else:
        # Unsupported file type
        return GAIAProcessedTask(
            task_entry=task_entry,
            processed_content=f"**Question:** {task_entry.question}\n\n**Note:** Attached file '{task_entry.file_name}' has unsupported format and cannot be processed.",
            content_type='unsupported',
            processing_method='none'
        )


def load_gaia_metadata(metadata_path: str) -> List[GAIAEntry]:
    """
    Load GAIA metadata from a JSONL file.
    
    Args:
        metadata_path: Path to the metadata.jsonl file
        
    Returns:
        List of GAIAEntry objects
    """
    entries = []
    
    if not os.path.exists(metadata_path):
        raise FileNotFoundError(f"Metadata file not found: {metadata_path}")
    
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    data = json.loads(line)
                    # Set file_path if file_name exists
                    if data.get("file_name"):
                        base_dir = os.path.dirname(metadata_path)
                        data["file_path"] = os.path.join(base_dir, data["file_name"])
                    
                    entry = GAIAEntry.from_dict(data)
                    entries.append(entry)
                    
                except json.JSONDecodeError as e:
                    print(f"Warning: Could not parse JSON on line {line_num}: {e}")
                    continue
                    
    except Exception as e:
        raise Exception(f"Error reading metadata file {metadata_path}: {e}")
    
    return entries


def load_gaia_tasks_blind(metadata_path: str) -> List[GAIATaskEntry]:
    """
    Load GAIA tasks WITHOUT answers from a JSONL file - for blind evaluation.
    
    Args:
        metadata_path: Path to the metadata.jsonl file
        
    Returns:
        List of GAIATaskEntry objects (without answers)
    """
    entries = []
    
    if not os.path.exists(metadata_path):
        raise FileNotFoundError(f"Metadata file not found: {metadata_path}")
    
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    data = json.loads(line)
                    # Set file_path if file_name exists
                    if data.get("file_name"):
                        base_dir = os.path.dirname(metadata_path)
                        data["file_path"] = os.path.join(base_dir, data["file_name"])
                    
                    # Create task entry WITHOUT answer data
                    entry = GAIATaskEntry.from_dict(data)
                    entries.append(entry)
                    
                except json.JSONDecodeError as e:
                    print(f"Warning: Could not parse JSON on line {line_num}: {e}")
                    continue
                    
    except Exception as e:
        raise Exception(f"Error reading metadata file {metadata_path}: {e}")
    
    return entries


def process_gaia_dataset(dataset_path: str, split: str = "test") -> List[GAIAProcessedEntry]:
    """
    Process an entire GAIA dataset split.
    
    Args:
        dataset_path: Path to the GAIA dataset directory
        split: Dataset split to process ('test' or 'validation')
        
    Returns:
        List of processed GAIA entries
    """
    metadata_path = os.path.join(dataset_path, "2023", split, "metadata.jsonl")
    
    # Load metadata
    gaia_entries = load_gaia_metadata(metadata_path)
    
    # Process each entry
    processed_entries = []
    for entry in gaia_entries:
        processed_entry = process_gaia_file(entry)
        processed_entries.append(processed_entry)
    
    return processed_entries


def format_gaia_entry_for_prisma(processed_entry: GAIAProcessedEntry) -> str:
    """
    Format a processed GAIA entry for input to Prisma system.
    
    Args:
        processed_entry: The processed GAIA entry
        
    Returns:
        Formatted string ready for Prisma processing
    """
    formatted = f"""# GAIA Task {processed_entry.gaia_entry.task_id}

**Level:** {processed_entry.gaia_entry.level}
**File Type:** {processed_entry.content_type}
**Processing Method:** {processed_entry.processing_method}

## Task Content:
{processed_entry.processed_content}

## Additional Metadata:
- Task ID: {processed_entry.gaia_entry.task_id}
- Expected Answer: {processed_entry.gaia_entry.final_answer}
- Attached File: {processed_entry.gaia_entry.file_name if processed_entry.gaia_entry.file_name else "None"}
"""

    # Add annotator metadata if available
    if processed_entry.gaia_entry.annotator_metadata:
        formatted += "\n## Annotator Notes:\n"
        for key, value in processed_entry.gaia_entry.annotator_metadata.items():
            if value:  # Only show non-empty metadata
                formatted += f"- {key}: {value}\n"
    
    return formatted


def format_gaia_task_for_prisma_blind(processed_task: GAIAProcessedTask) -> str:
    """
    Format a processed GAIA task for input to Prisma system WITHOUT revealing answers.
    
    Args:
        processed_task: The processed GAIA task (without answers)
        
    Returns:
        Formatted string ready for Prisma processing (blind evaluation)
    """
    formatted = f"""# GAIA Task {processed_task.task_entry.task_id}

**Level:** {processed_task.task_entry.level}
**File Type:** {processed_task.content_type}
**Processing Method:** {processed_task.processing_method}

## Task Content:
{processed_task.processed_content}

## Task Metadata:
- Task ID: {processed_task.task_entry.task_id}
- Difficulty Level: {processed_task.task_entry.level}
- Attached File: {processed_task.task_entry.file_name if processed_task.task_entry.file_name else "None"}

---
**Instructions:** Please provide your final answer to this GAIA task. Be thorough and precise in your reasoning.
"""
    
    return formatted

