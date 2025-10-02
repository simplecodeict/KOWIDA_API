"""
Translation Service using Facebook's NLLB model for Korean to English translation.
This service provides unlimited, free translation capabilities for Korean text to English.
"""

import logging
import time
from typing import Optional, Dict, Any
from functools import lru_cache
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor
import queue

logger = logging.getLogger(__name__)

class TranslationService:
    """
    Translation service using Facebook's NLLB model.
    Supports Korean to English translation with caching for performance.
    """
    
    def __init__(self):
        self.model_name = "facebook/nllb-200-distilled-600M"
        self.tokenizer = None
        self.model = None
        self.translator = None
        self.sinhala_translator = None  # For English to Sinhala
        self._lock = threading.Lock()
        self._initialized = False
        
        # Performance optimizations for high-volume usage
        self.executor = ThreadPoolExecutor(max_workers=4)  # Adjust based on your server capacity
        self.request_queue = queue.Queue(maxsize=100)  # Limit concurrent requests
        self.active_requests = 0
        self.max_concurrent_requests = 10  # Adjust based on your server capacity
        
    def _initialize_model(self):
        """Initialize the NLLB model and tokenizer."""
        if self._initialized:
            return
            
        with self._lock:
            if self._initialized:
                return
                
            try:
                logger.info("Initializing NLLB translation model...")
                start_time = time.time()
                
                # Load tokenizer and model
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                self.model = AutoModelForSeq2SeqLM.from_pretrained(
                    self.model_name,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    device_map="auto" if torch.cuda.is_available() else None
                )
                
                # Create Korean to English translation pipeline
                self.translator = pipeline(
                    "translation",
                    model=self.model,
                    tokenizer=self.tokenizer,
                    src_lang="kor_Hang",  # Korean
                    tgt_lang="eng_Latn",  # English
                    max_length=512,
                    device=0 if torch.cuda.is_available() else -1
                )
                
                # Create English to Sinhala translation pipeline
                self.sinhala_translator = pipeline(
                    "translation",
                    model=self.model,
                    tokenizer=self.tokenizer,
                    src_lang="eng_Latn",  # English
                    tgt_lang="sin_Sinh",  # Sinhala
                    max_length=512,
                    device=0 if torch.cuda.is_available() else -1
                )
                
                self._initialized = True
                init_time = time.time() - start_time
                logger.info(f"NLLB model initialized successfully in {init_time:.2f} seconds")
                
            except Exception as e:
                logger.error(f"Failed to initialize NLLB model: {e}")
                raise
    
    @lru_cache(maxsize=5000)  # Increased cache size for better performance
    def translate_cached(self, text: str) -> str:
        """
        Translate Korean text to English with caching.
        Cache is limited to 5000 entries to manage memory usage and improve performance.
        """
        return self._translate_uncached(text)
    
    @lru_cache(maxsize=5000)  # Cache for English to Sinhala translations
    def translate_english_to_sinhala_cached(self, text: str) -> str:
        """
        Translate English text to Sinhala with caching.
        Cache is limited to 5000 entries to manage memory usage and improve performance.
        """
        return self._translate_english_to_sinhala_uncached(text)
    
    def _translate_uncached(self, text: str) -> str:
        """Internal method for actual translation without caching."""
        if not self._initialized:
            self._initialize_model()
        
        try:
            # Clean and validate input
            text = text.strip()
            if not text:
                return ""
            
            # Translate using NLLB pipeline
            result = self.translator(text, max_length=512, num_beams=4, early_stopping=True)
            
            if result and len(result) > 0:
                translated_text = result[0]['translation_text']
                logger.debug(f"Translated: '{text[:50]}...' -> '{translated_text[:50]}...'")
                return translated_text
            else:
                logger.warning(f"Translation returned empty result for: {text[:50]}...")
                return text  # Return original text if translation fails
                
        except Exception as e:
            logger.error(f"Translation error for text '{text[:50]}...': {e}")
            return text  # Return original text on error
    
    def _translate_english_to_sinhala_uncached(self, text: str) -> str:
        """Internal method for English to Sinhala translation without caching."""
        if not self._initialized:
            self._initialize_model()
        
        try:
            # Clean and validate input
            text = text.strip()
            if not text:
                return ""
            
            # Translate using NLLB pipeline
            result = self.sinhala_translator(text, max_length=512, num_beams=4, early_stopping=True)
            
            if result and len(result) > 0:
                translated_text = result[0]['translation_text']
                logger.debug(f"Translated EN->SI: '{text[:50]}...' -> '{translated_text[:50]}...'")
                return translated_text
            else:
                logger.warning(f"EN->SI Translation returned empty result for: {text[:50]}...")
                return text  # Return original text if translation fails
                
        except Exception as e:
            logger.error(f"EN->SI Translation error for text '{text[:50]}...': {e}")
            return text  # Return original text on error
    
    def translate(self, text: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Translate Korean text to English.
        
        Args:
            text (str): Korean text to translate
            use_cache (bool): Whether to use caching for better performance
            
        Returns:
            Dict containing translation result and metadata
        """
        start_time = time.time()
        
        try:
            # Validate input
            if not text or not isinstance(text, str):
                return {
                    'success': False,
                    'error': 'Invalid input text',
                    'original_text': text,
                    'translated_text': '',
                    'processing_time': 0
                }
            
            # Perform translation
            if use_cache:
                translated_text = self.translate_cached(text)
            else:
                translated_text = self._translate_uncached(text)
            
            processing_time = time.time() - start_time
            
            return {
                'success': True,
                'original_text': text,
                'translated_text': translated_text,
                'source_language': 'Korean',
                'target_language': 'English',
                'processing_time': round(processing_time, 3),
                'model': 'NLLB-200-distilled-600M'
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Translation service error: {e}")
            
            return {
                'success': False,
                'error': str(e),
                'original_text': text,
                'translated_text': '',
                'processing_time': round(processing_time, 3)
            }
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model."""
        return {
            'model_name': self.model_name,
            'initialized': self._initialized,
            'device': 'cuda' if torch.cuda.is_available() else 'cpu',
            'cache_size': self.translate_cached.cache_info().currsize if self._initialized else 0,
            'cache_maxsize': self.translate_cached.cache_info().maxsize if self._initialized else 0
        }
    
    def clear_cache(self):
        """Clear the translation cache."""
        if self._initialized:
            self.translate_cached.cache_clear()
            logger.info("Translation cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring."""
        if self._initialized:
            cache_info = self.translate_cached.cache_info()
            return {
                'hits': cache_info.hits,
                'misses': cache_info.misses,
                'current_size': cache_info.currsize,
                'max_size': cache_info.maxsize,
                'hit_rate': cache_info.hits / (cache_info.hits + cache_info.misses) if (cache_info.hits + cache_info.misses) > 0 else 0
            }
        return {}
    
    def translate_async(self, text: str, use_cache: bool = True):
        """
        Asynchronous translation for better performance with high concurrent requests.
        Returns a future that can be awaited.
        """
        return self.executor.submit(self.translate, text, use_cache)
    
    def translate_korean_to_both(self, text: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Translate Korean text to both English and Sinhala.
        
        Args:
            text (str): Korean text to translate
            use_cache (bool): Whether to use caching for better performance
            
        Returns:
            Dict containing both English and Sinhala translations
        """
        start_time = time.time()
        
        try:
            # Validate input
            if not text or not isinstance(text, str):
                return {
                    'success': False,
                    'error': 'Invalid input text',
                    'original_text': text,
                    'english_text': '',
                    'sinhala_text': '',
                    'processing_time': 0
                }
            
            # First translate Korean to English
            if use_cache:
                english_text = self.translate_cached(text)
            else:
                english_text = self._translate_uncached(text)
            
            # Then translate English to Sinhala
            if use_cache:
                sinhala_text = self.translate_english_to_sinhala_cached(english_text)
            else:
                sinhala_text = self._translate_english_to_sinhala_uncached(english_text)
            
            processing_time = time.time() - start_time
            
            return {
                'success': True,
                'original_text': text,
                'english_text': english_text,
                'sinhala_text': sinhala_text,
                'source_language': 'Korean',
                'target_languages': ['English', 'Sinhala'],
                'processing_time': round(processing_time, 3),
                'model': 'NLLB-200-distilled-600M'
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Korean to both translation service error: {e}")
            
            return {
                'success': False,
                'error': str(e),
                'original_text': text,
                'english_text': '',
                'sinhala_text': '',
                'processing_time': round(processing_time, 3)
            }

# Global instance
translation_service = TranslationService()
