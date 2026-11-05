# requirements.txt
"""
gradio
sentence-transformers
transformers
torch
PyPDF2
pdfplumber
python-docx
nltk
rake-nltk
scikit-learn
pandas
numpy
"""
import logging
import re
import time
from pathlib import Path
from typing import List, Dict

import docx
import nltk
import numpy as np
import pandas as pd
import pdfplumber
import torch
from rake_nltk import Rake
from sentence_transformers import SentenceTransformer, CrossEncoder
from sklearn.metrics.pairwise import cosine_similarity

# Download required NLTK data
nltk.download('stopwords')
nltk.download('wordnet')
nltk.download('omw-1.4')
nltk.download('punkt')
nltk.download('punkt_tab')

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
"""
here the lighter version of SBERT is being used :  sentence_model_name: str = 'all-MiniLM-L6-v2'
here the heavier version of BERT  is being  used :  cross_encoder_model_name: str = 'cross-encoder/ms-marco-MiniLM-L-12-v2'
"""


class ResumeScreeningSystem:
    def __init__(self,
                 sentence_model_name: str = 'all-MiniLM-L6-v2',  # 'all-mpnet-base-v2' (comment is heavier)
                 cross_encoder_model_name: str = 'cross-encoder/ms-marco-MiniLM-L-12-v2',
                 # 'cross-encoder/ms-marco-MiniLM-L-6-v2' (comment is lighter)
                 top_n: int = 100,
                 device: str = 'cpu'):
        """
        Initialize the Resume Screening System with specified models.

        Args:
            sentence_model_name: Sentence-BERT model for initial screening
            cross_encoder_model_name: Cross-Encoder model for reranking
            top_n: Number of candidates to pass to Cross-Encoder
            device: 'cpu' or 'cuda'
        """
        self.device = device if torch.cuda.is_available() and device == 'cuda' else 'cpu'
        logger.info(f"Using device: {self.device}")

        # Initialize models
        self.sentence_model = SentenceTransformer(sentence_model_name, device=self.device)
        self.cross_encoder = CrossEncoder(cross_encoder_model_name, device=self.device)
        self.top_n = top_n
        # Initialize RAKE for keyword extraction
        self.rake = Rake()

        # Preprocessing components
        self.stopwords = set(nltk.corpus.stopwords.words('english'))
        self.lemmatizer = nltk.stem.WordNetLemmatizer()

        # Results storage
        self.results = None

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract raw text from a PDF file."""
        try:
            text = ""
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text.strip()
        except Exception as e:
            logger.error(f"Error extracting text from {pdf_path}: {e}")
            return ""

    def extract_text_from_file(self, file_path: str) -> str:
        """Extract raw text from a PDF or DOCX file."""
        try:
            lower = file_path.lower()
            if lower.endswith(".pdf"):
                return self.extract_text_from_pdf(file_path)
            elif lower.endswith(".docx"):
                document = docx.Document(file_path)
                return "\n".join(p.text for p in document.paragraphs).strip()
            elif lower.endswith(".doc"):
                logger.warning(f"Legacy .doc not supported (please save as .docx): {file_path}")
                return ""
            else:
                logger.warning(f"Unsupported file type: {file_path}")
                return ""
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {e}")
            return ""

    def preprocess_text(self, text: str) -> str:
        """
        Comprehensive preprocessing:
        - Lowercasing
        - Remove special characters
        - Tokenization
        - Stopword removal
        - Lemmatization
        """
        # Lowercase
        text = text.lower()

        # Remove special characters but keep alphanumeric and spaces
        text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)

        # Tokenize
        tokens = nltk.word_tokenize(text)

        # Remove stopwords and lemmatize
        processed_tokens = []
        for token in tokens:
            if token not in self.stopwords and len(token) > 2:
                lemma = self.lemmatizer.lemmatize(token)
                processed_tokens.append(lemma)
        print(processed_tokens)  # use these  for filtering
        return ' '.join(processed_tokens)

    def process_resume_files(self, file_paths: List[str]) -> Dict:
        """Process a list of PDF/DOCX resume file paths."""
        resume_data = {}

        if not file_paths:
            raise ValueError("No resume files provided")

        logger.info(f"Processing {len(file_paths)} resume files")

        for path in file_paths:
            try:
                pdf_path = Path(path)
                raw_text = self.extract_text_from_file(str(pdf_path))
                if not raw_text:
                    continue

                processed_text = self.preprocess_text(raw_text)

                resume_data[str(pdf_path)] = {
                    'filename': pdf_path.name,
                    'raw_text': raw_text,
                    'processed_text': processed_text,
                }
                logger.info(f"Processed: {pdf_path.name}")
            except Exception as e:
                logger.error(f"Error processing {path}: {e}")
                continue

        return resume_data

    def compute_embeddings(self, texts: List[str]) -> np.ndarray:
        """Compute embeddings for a list of texts."""
        return self.sentence_model.encode(texts, convert_to_tensor=False)

    def extract_keywords(self, text: str, top_k: int = 30) -> List[str]:
        """Extract keywords using RAKE."""
        self.rake.extract_keywords_from_text(text)
        keywords = self.rake.get_ranked_phrases()[:top_k]
        return keywords

    def screen_resumes(self, resume_files: List[str], job_description: str,
                       use_reranker: bool = True) -> pd.DataFrame:
        """
        Main screening pipeline:
        1. Process resumes
        2. Generate embeddings
        3. Calculate similarities
        4. Select top N
        5. (Optional) Rerank with Cross-Encoder
        6. Extract keywords
        7. Categorize candidates
        """
        logger.info(f"Starting resume screening process... (reranker={'ON' if use_reranker else 'OFF'})")

        # Step 1: Process resumes
        resume_data = self.process_resume_files(resume_files)

        if not resume_data:
            raise ValueError("No resumes could be processed successfully")

        # Step 2: Preprocess job description
        processed_jd = self.preprocess_text(job_description)
        logger.info(f"Processed job description: {len(processed_jd)} characters")

        start_time_resume_screening = time.time()

        # Step 3: Generate embeddings for all resumes
        resume_texts = [data['processed_text'] for data in resume_data.values()]
        resume_embeddings = self.compute_embeddings(resume_texts)

        print("Time taken to screen all resumes --- %s seconds ---"
              % (time.time() - start_time_resume_screening))

        jd_embedding = self.compute_embeddings([processed_jd])[0]

        # Step 4: Calculate cosine similarities
        similarities = cosine_similarity(
            resume_embeddings, jd_embedding.reshape(1, -1)
        ).flatten()

        # Step 5: Create initial results
        results = []
        for (pdf_path, data), similarity in zip(resume_data.items(), similarities):
            results.append({
                'pdf_path': pdf_path,
                'filename': data['filename'],
                'initial_similarity': float(similarity),
                'raw_text': data['raw_text'],
                'processed_text': data['processed_text']
            })

        # Sort by initial similarity
        results.sort(key=lambda x: x['initial_similarity'], reverse=True)

        # Step 6: Select top N candidates
        top_results = results[:self.top_n]

        if use_reranker:
            logger.info(f"Selected top {len(top_results)} candidates for Cross-Encoder reranking")
            start_time_crossencoder_reranking = time.time()

            if top_results:
                pairs = [(job_description, r['raw_text']) for r in top_results]
                cross_scores = self.cross_encoder.predict(pairs)
                for result, score in zip(top_results, cross_scores):
                    result['cross_encoder_score'] = float(score)
                top_results.sort(key=lambda x: x['cross_encoder_score'], reverse=True)
                print("Time taken to re-rank using cross encoder BERT --- %s seconds ---"
                      % (time.time() - start_time_crossencoder_reranking))
        else:
            logger.info("Reranker OFF — using Sentence-BERT similarity only.")
            # Keep same keys so downstream code doesn't KeyError
            for r in top_results:
                r['cross_encoder_score'] = None

        # Step 7: Extract keywords (independent of reranker)
        for result in top_results:
            result['keywords'] = self.extract_keywords(result['raw_text'])

            if use_reranker and result['cross_encoder_score'] is not None:
                score = result['cross_encoder_score']
                if score >= 0.7:
                    result['category'] = 'Strong Match'
                elif score >= 0.4:
                    result['category'] = 'Partial Match'
                else:
                    result['category'] = 'Weak Match'
            else:
                result['category'] = 'N/A (Reranker OFF)'

        # Store results — full data kept regardless of display.
        # We also attach the FULL keyword list (not just top-5) on the DataFrame
        # via .attrs so the viewer can highlight every keyword, not just 5.
        rows = []
        full_keyword_lists = []
        for i, r in enumerate(top_results):
            rows.append({
                'row_id': i,
                'Candidate Name': r['filename'].replace('.pdf', '').replace('.docx', ''),
                'Initial Similarity Score': r.get('initial_similarity', 0),
                'Final Cross-Encoder Score': (
                    r.get('cross_encoder_score')
                    if r.get('cross_encoder_score') is not None
                    else float('nan')
                ),
                'Category': r.get('category', 'Not Processed'),
                'Extracted Keywords': ', '.join(r.get('keywords', [])[:5]),  # display: top 5
                'PDF Path': r['pdf_path'],
            })
            full_keyword_lists.append(list(r.get('keywords', [])))  # FULL list

        self.results = pd.DataFrame(rows)

        # .attrs survives DataFrame slicing and is carried in gr.State.
        # We store the full keyword list per row here.
        self.results.attrs['full_keywords'] = full_keyword_lists

        logger.info(f"Screening complete. Found {len(self.results)} candidates.")
        return self.results