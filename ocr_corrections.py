"""
OCR Text Corrections Module
Comprehensive corrections for Korean and English text extracted from images
"""

# Korean text corrections - organized by category for better maintainability
KOREAN_CORRECTIONS = {
    # Common OCR mistakes for basic Korean words
    '오라인': '온라인',
    '쇼핑물올': '쇼핑몰을',
    '쇼핑물에서논': '쇼핑몰에서는',
    '쇼풍물올': '쇼핑몰을',
    '쇼{다T': '쇼핑몰을',
    '쇼청-어서논': '쇼핑몰에서는',
    
    # Shopping and products
    '생필품올': '생필품을',
    '생필품을구입하는': '생필품을 구입하는',
    '상품올': '상품을',
    '상품을': '상품을',
    '상표다': '상품을',
    '상5': '상품',
    '상5자': '상품을',
    '상8': '상품',
    
    # Discounts and sales
    '할인올': '할인을',
    '할인을': '할인을',
    '할인율': '할인을',
    '할인': '할인',
    '훨언': '할인',
    '나인': '할인',
    '밥인': '할인',
    '나언': '할인',
    '꽤인': '할인',
    '거인속': '할인을',
    
    # Events and activities
    '행사클': '행사를',
    '행사람': '행사를',
    '행사를': '행사를',
    '7사사': '행사를',
    '법사다': '행사를',
    '법사어': '행사에',
    
    # Coupons and offers
    '구돈을': '쿠폰을',
    '구품올': '쿠폰을',
    '무존하': '쿠폰을',
    
    # Actions and verbs
    '받울': '받을',
    '받을': '받을',
    '받$': '받을',
    '수있습니다': '수 있습니다',
    '수 있심니다': '수 있습니다',
    '수있속니다': '수 있습니다',
    '얻을수': '얻을 수',
    '언기': '얻을',
    
    # Shopping methods
    '알플하게': '알뜰하게',
    '알뜰하게': '알뜰하게',
    '한국에서알뜰하게생필품을': '한국에서 알뜰하게 생필품을',
    '구입하는팁': '구입하는 팁',
    '틱': '팁',
    
    # Stores and locations
    '마드예서는': '마트에서는',
    '마트에서는': '마트에서는',
    '마루어서논': '마트에서는',
    '대침': '대형',
    '미르어서': '마트에서',
    
    # Frequency and time
    '좀종': '종종',
    '중중': '종종',
    '정기적오로': '정기적으로',
    '정기적으로': '정기적으로',
    '주업': '주말',
    
    # Special offers
    '가회': '특가',
    '가은': '같은',
    '업어서': '열어서',
    
    # Food and daily necessities
    '식': '식품',
    '료품부터': '식료품부터',
    '코티부터': '식료품부터',
    '심사8공가치': '생활용품까지',
    
    # Descriptions
    '다양하': '다양한',
    '다양한': '다양한',
    '씨게': '싸게',
    '싸거': '싸게',
    '싸거판어라니다': '싸게 판매합니다',
    '씨거구머하거나': '싸게 구매하거나',
    
    # Information and communication
    '전단지골': '전단지를',
    '천단치a': '전단지를',
    '정보올': '정보를',
    '점보화': '정보를',
    '남벼': '통해',
    '국석서도': '통해서도',
    '심차표$': '생필품을',
    '구머n': '구매할',
    
    # Pronouns and particles
    '이틀': '이를',
    '이를': '이를',
    '이꼴': '이를',
    '이뇨': '이를',
    '확용하여': '활용하여',
    '부용하여': '활용하여',
    
    # Specific terms
    '수청': '특정',
    '추가': '추가',
    '금외': '금액',
    '추선': '추천',
    '급': '등',
    '디한': '대한',
    '나누어주': '나누어 주는',
    
    # Common OCR character mistakes
    '온라언': '온라인',
    '세공합니다': '제공합니다',
    '저공나나다': '제공합니다',
}

# English text corrections - organized by category (COMMENTED OUT - Korean only for now)
# ENGLISH_CORRECTIONS = {
#     # Common OCR mistakes for basic English words
#     'Yarious': 'Various',
#     'bout': 'about',
#     'Yo can': 'You can',
#     'al5o': 'also',
#     'Cnline': 'Online',
#     'mlalb': 'malls',
#     'coupans': 'coupons',
#     
#     # Shopping and retail terms
#     'recommnendations': 'recommendations',
#     'inflyers': 'in flyers',
#     'superrmarkets': 'supermarkets',
#     'discaunt': 'discount',
#     'disciunt': 'discount',
#     'Itcm$': 'items',
#     'prlcts': 'prices',
#     'tRd': 'and',
#     
#     # Common character substitutions
#     '5': 's',  # Common OCR mistake
#     '0': 'o',  # Common OCR mistake
#     '1': 'l',  # Common OCR mistake
#     '8': 'B',  # Common OCR mistake
#     '3': 'E',  # Common OCR mistake
# }

# Advanced corrections for complex patterns
ADVANCED_KOREAN_PATTERNS = [
    # Pattern: [Korean word][Korean word] -> [Korean word] [Korean word] (add space)
    (r'([가-힣])([가-힣])([을를이가은는도만부터까지에서의와과])', r'\1\2 \3'),
    
    # Pattern: Fix common spacing issues
    (r'([가-힣])([a-zA-Z])', r'\1 \2'),
    (r'([a-zA-Z])([가-힣])', r'\1 \2'),
]

# Performance optimization: Create lookup sets for faster processing
KOREAN_CORRECTIONS_SET = set(KOREAN_CORRECTIONS.keys())
# ENGLISH_CORRECTIONS_SET = set(ENGLISH_CORRECTIONS.keys())  # Commented out - Korean only

def apply_korean_corrections(text):
    """
    Apply Korean text corrections efficiently
    """
    if not text:
        return text
    
    # Apply direct corrections
    for wrong, correct in KOREAN_CORRECTIONS.items():
        if wrong in text:
            text = text.replace(wrong, correct)
    
    return text

def apply_english_corrections(text):
    """
    Apply English text corrections efficiently (COMMENTED OUT - Korean only for now)
    """
    # English corrections disabled - Korean only mode
    return text
    
    # if not text:
    #     return text
    # 
    # # Apply direct corrections
    # for wrong, correct in ENGLISH_CORRECTIONS.items():
    #     if wrong in text:
    #         text = text.replace(wrong, correct)
    # 
    # return text

def apply_all_corrections(korean_text, english_text):
    """
    Apply all corrections to both Korean and English text
    Optimized for performance
    """
    # Apply corrections
    corrected_korean = apply_korean_corrections(korean_text)
    corrected_english = apply_english_corrections(english_text)
    
    # Clean up extra spaces
    corrected_korean = ' '.join(corrected_korean.split())
    corrected_english = ' '.join(corrected_english.split())
    
    return corrected_korean, corrected_english

def add_correction(korean_wrong=None, korean_correct=None, english_wrong=None, english_correct=None):
    """
    Dynamically add new corrections at runtime (Korean only mode)
    """
    if korean_wrong and korean_correct:
        KOREAN_CORRECTIONS[korean_wrong] = korean_correct
        KOREAN_CORRECTIONS_SET.add(korean_wrong)
    
    # English corrections disabled - Korean only mode
    # if english_wrong and english_correct:
    #     ENGLISH_CORRECTIONS[english_wrong] = english_correct
    #     ENGLISH_CORRECTIONS_SET.add(english_wrong)

def get_correction_stats():
    """
    Get statistics about available corrections
    """
    return {
        'korean_corrections': len(KOREAN_CORRECTIONS),
        'english_corrections': 0,  # Disabled - Korean only mode
        'total_corrections': len(KOREAN_CORRECTIONS)
    }

# Pre-compile for better performance
import re
COMPILED_PATTERNS = [(re.compile(pattern), replacement) for pattern, replacement in ADVANCED_KOREAN_PATTERNS]

def apply_advanced_corrections(text):
    """
    Apply advanced pattern-based corrections
    """
    for pattern, replacement in COMPILED_PATTERNS:
        text = pattern.sub(replacement, text)
    return text
