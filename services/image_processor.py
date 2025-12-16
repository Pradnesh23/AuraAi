"""
Image preprocessing service using OpenCV
Handles denoising, deskewing, and enhancement for better OCR results
"""
import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class ImageProcessor:
    """OpenCV-based image preprocessing for OCR optimization"""
    
    def __init__(self):
        self.target_dpi = 300
    
    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """
        Full preprocessing pipeline for resume images
        
        Args:
            image: Input image as numpy array (BGR format)
            
        Returns:
            Preprocessed image optimized for OCR
        """
        # Convert to grayscale
        gray = self._to_grayscale(image)
        
        # Denoise
        denoised = self._denoise(gray)
        
        # Deskew if needed
        deskewed = self._deskew(denoised)
        
        # Enhance contrast
        enhanced = self._enhance_contrast(deskewed)
        
        # Binarize for OCR
        binary = self._binarize(enhanced)
        
        return binary
    
    def _to_grayscale(self, image: np.ndarray) -> np.ndarray:
        """Convert image to grayscale if needed"""
        if len(image.shape) == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image
    
    def _denoise(self, image: np.ndarray) -> np.ndarray:
        """
        Apply denoising using Non-local Means Denoising
        Effective for scanned documents with noise
        """
        # Use fastNlMeansDenoising for grayscale images
        denoised = cv2.fastNlMeansDenoising(
            image,
            None,
            h=10,  # Filter strength
            templateWindowSize=7,
            searchWindowSize=21
        )
        return denoised
    
    def _deskew(self, image: np.ndarray) -> np.ndarray:
        """
        Detect and correct skew in document images
        Uses Hough Line Transform to find dominant angle
        """
        # Detect edges
        edges = cv2.Canny(image, 50, 150, apertureSize=3)
        
        # Detect lines using Hough Transform
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=100,
            minLineLength=100,
            maxLineGap=10
        )
        
        if lines is None:
            return image
        
        # Calculate angles of detected lines
        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi
            # Only consider near-horizontal lines
            if abs(angle) < 45:
                angles.append(angle)
        
        if not angles:
            return image
        
        # Get median angle (more robust than mean)
        median_angle = np.median(angles)
        
        # Only correct if skew is significant
        if abs(median_angle) < 0.5:
            return image
        
        # Rotate to correct skew
        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        
        # Calculate new image bounds
        cos = np.abs(rotation_matrix[0, 0])
        sin = np.abs(rotation_matrix[0, 1])
        new_w = int((h * sin) + (w * cos))
        new_h = int((h * cos) + (w * sin))
        
        rotation_matrix[0, 2] += (new_w / 2) - center[0]
        rotation_matrix[1, 2] += (new_h / 2) - center[1]
        
        rotated = cv2.warpAffine(
            image,
            rotation_matrix,
            (new_w, new_h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )
        
        logger.debug(f"Corrected skew of {median_angle:.2f} degrees")
        return rotated
    
    def _enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """
        Enhance contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization)
        Works well for documents with uneven lighting
        """
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(image)
        return enhanced
    
    def _binarize(self, image: np.ndarray) -> np.ndarray:
        """
        Apply adaptive thresholding for binarization
        Better than global thresholding for documents
        """
        binary = cv2.adaptiveThreshold(
            image,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=11,
            C=2
        )
        return binary
    
    def remove_borders(self, image: np.ndarray, border_size: int = 5) -> np.ndarray:
        """Remove dark borders from scanned documents"""
        h, w = image.shape[:2]
        return image[border_size:h-border_size, border_size:w-border_size]
    
    def resize_for_ocr(
        self, 
        image: np.ndarray, 
        target_height: int = 2000
    ) -> np.ndarray:
        """
        Resize image to optimal size for OCR
        Maintains aspect ratio
        """
        h, w = image.shape[:2]
        if h < target_height:
            scale = target_height / h
            new_w = int(w * scale)
            resized = cv2.resize(
                image, 
                (new_w, target_height), 
                interpolation=cv2.INTER_CUBIC
            )
            return resized
        return image
    
    def load_image(self, path: Path) -> Optional[np.ndarray]:
        """Load image from file path"""
        try:
            image = cv2.imread(str(path))
            if image is None:
                logger.error(f"Failed to load image: {path}")
                return None
            return image
        except Exception as e:
            logger.error(f"Error loading image {path}: {e}")
            return None
    
    def save_processed(
        self, 
        image: np.ndarray, 
        output_path: Path
    ) -> bool:
        """Save processed image to disk"""
        try:
            cv2.imwrite(str(output_path), image)
            return True
        except Exception as e:
            logger.error(f"Error saving image {output_path}: {e}")
            return False
