from typing import Dict, List
import re
from textstat import textstat

class ReadabilityScorer:
    """Analyzes and scores documentation readability."""
    
    GRADE_LEVELS = {
        'easy': 8.0,      # 8th grade reading level
        'medium': 12.0,   # 12th grade reading level
        'hard': 16.0      # College level
    }
    
    def __init__(self):
        self.scores: Dict[str, Dict] = {}
    
    def analyze_text(self, text: str, section_name: str) -> Dict:
        """Analyze text and return readability metrics."""
        metrics = {
            'flesch_reading_ease': textstat.flesch_reading_ease(text),
            'flesch_kincaid_grade': textstat.flesch_kincaid_grade(text),
            'gunning_fog': textstat.gunning_fog(text),
            'avg_sentence_length': self._average_sentence_length(text),
            'complex_word_percentage': self._complex_word_percentage(text),
            'paragraphs': len(text.split('\n\n')),
        }
        
        # Store scores for later reference
        self.scores[section_name] = metrics
        return metrics
    
    def get_recommendations(self, section_name: str) -> List[str]:
        """Get improvement recommendations based on scores."""
        if section_name not in self.scores:
            return []
        
        metrics = self.scores[section_name]
        recommendations = []
        
        if metrics['flesch_reading_ease'] < 60:
            recommendations.append("Consider simplifying language for better readability")
        
        if metrics['avg_sentence_length'] > 25:
            recommendations.append("Try breaking up longer sentences")
        
        if metrics['complex_word_percentage'] > 20:
            recommendations.append("Use simpler words where possible")
        
        if metrics['paragraphs'] < 2:
            recommendations.append("Consider breaking content into more paragraphs")
        
        return recommendations
    
    def _average_sentence_length(self, text: str) -> float:
        """Calculate average sentence length."""
        sentences = re.split(r'[.!?]+', text)
        words = len(text.split())
        return words / len(sentences) if sentences else 0
    
    def _complex_word_percentage(self, text: str) -> float:
        """Calculate percentage of complex words (3+ syllables)."""
        words = text.split()
        complex_words = sum(1 for word in words if textstat.syllable_count(word) >= 3)
        return (complex_words / len(words) * 100) if words else 0
    
    def is_section_readable(self, section_name: str, target_level: str = 'medium') -> bool:
        """Check if section meets target readability level."""
        if section_name not in self.scores:
            return False
        
        metrics = self.scores[section_name]
        target_grade = self.GRADE_LEVELS[target_level]
        
        return (
            metrics['flesch_kincaid_grade'] <= target_grade and
            metrics['gunning_fog'] <= target_grade + 2
        ) 