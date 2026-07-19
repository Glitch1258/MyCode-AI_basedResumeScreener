# requirements.txt
"""
gradio
sentence-transformers
transformers
torch
PyPDF2
pdfplumber
nltk
rake-nltk
scikit-learn
pandas
numpy
"""

import os
import re
import nltk
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import gradio as gr
import pdfplumber
from sentence_transformers import SentenceTransformer, CrossEncoder
from sklearn.metrics.pairwise import cosine_similarity
from rake_nltk import Rake
import torch
import logging
from datetime import datetime

# Download required NLTK data
nltk.download('stopwords')
nltk.download('wordnet')
nltk.download('omw-1.4')
nltk.download('punkt')
nltk.download('punkt_tab')

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ResumeScreeningSystem:
    def __init__(self, 
                 sentence_model_name: str = 'all-MiniLM-L6-v2',
                 cross_encoder_model_name: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2',
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
        
        return ' '.join(processed_tokens)
    
    def process_resume_folder(self, folder_path: str) -> Dict:
        """Process all PDFs in a folder."""
        resume_data = {}
        pdf_files = list(Path(folder_path).glob('*.pdf'))
        
        if not pdf_files:
            raise ValueError(f"No PDF files found in {folder_path}")
        
        logger.info(f"Found {len(pdf_files)} PDF files")
        
        for pdf_path in pdf_files:
            try:
                # Extract raw text
                raw_text = self.extract_text_from_pdf(str(pdf_path))
                if not raw_text:
                    continue
                
                # Preprocess text
                processed_text = self.preprocess_text(raw_text)
                
                # Store both raw and processed text
                resume_data[str(pdf_path)] = {
                    'filename': pdf_path.name,
                    'raw_text': raw_text,
                    'processed_text': processed_text,
                }
                logger.info(f"Processed: {pdf_path.name}")
            except Exception as e:
                logger.error(f"Error processing {pdf_path.name}: {e}")
                continue
        
        return resume_data
    
    def compute_embeddings(self, texts: List[str]) -> np.ndarray:
        """Compute embeddings for a list of texts."""
        return self.sentence_model.encode(texts, convert_to_tensor=False)
    
    def extract_keywords(self, text: str, top_k: int = 10) -> List[str]:
        """Extract keywords using RAKE."""
        self.rake.extract_keywords_from_text(text)
        keywords = self.rake.get_ranked_phrases()[:top_k]
        return keywords
    
    def screen_resumes(self, resume_folder: str, job_description: str) -> pd.DataFrame:
        """
        Main screening pipeline:
        1. Process resumes
        2. Generate embeddings
        3. Calculate similarities
        4. Select top N
        5. Rerank with Cross-Encoder
        6. Extract keywords
        7. Categorize candidates
        """
        logger.info("Starting resume screening process...")
        
        # Step 1: Process resumes
        resume_data = self.process_resume_folder(resume_folder)
        if not resume_data:
            raise ValueError("No resumes could be processed successfully")
        
        # Step 2: Preprocess job description
        processed_jd = self.preprocess_text(job_description)
        logger.info(f"Processed job description: {len(processed_jd)} characters")
        
        # Step 3: Generate embeddings for all resumes
        resume_texts = [data['processed_text'] for data in resume_data.values()]
        resume_embeddings = self.compute_embeddings(resume_texts)
        
        # Generate embedding for job description
        jd_embedding = self.compute_embeddings([processed_jd])[0]
        
        # Step 4: Calculate cosine similarities
        similarities = cosine_similarity(resume_embeddings, jd_embedding.reshape(1, -1)).flatten()
        
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
        logger.info(f"Selected top {len(top_results)} candidates for Cross-Encoder reranking")
        
        # Step 7: Cross-Encoder reranking
        if top_results:
            # Prepare pairs for Cross-Encoder
            pairs = [(job_description, result['raw_text']) for result in top_results]
            cross_scores = self.cross_encoder.predict(pairs)
            
            # Update results with Cross-Encoder scores
            for result, score in zip(top_results, cross_scores):
                result['cross_encoder_score'] = float(score)
            
            # Rerank based on Cross-Encoder scores
            top_results.sort(key=lambda x: x['cross_encoder_score'], reverse=True)
            
            # Step 8: Extract keywords and categorize
            for result in top_results:
                result['keywords'] = self.extract_keywords(result['raw_text'])
                
                # Step 9: Categorize candidates
                score = result['cross_encoder_score']
                if score >= 0.7:
                    result['category'] = 'Strong Match'
                elif score >= 0.4:
                    result['category'] = 'Partial Match'
                else:
                    result['category'] = 'Weak Match'
        
        # Store results
        self.results = pd.DataFrame([
            {
                'Candidate Name': r['filename'].replace('.pdf', ''),
                'Initial Similarity Score': r.get('initial_similarity', 0),
                'Final Cross-Encoder Score': r.get('cross_encoder_score', 0),
                'Category': r.get('category', 'Not Processed'),
                'Extracted Keywords': ', '.join(r.get('keywords', [])[:5]),
                'PDF Path': r['pdf_path']
            }
            for r in top_results
        ])
        
        logger.info(f"Screening complete. Found {len(self.results)} candidates.")
        return self.results

def create_gradio_interface():
    """Create the Gradio UI interface."""
    
    system = None
    
    def process_resumes(resume_folder, job_description, top_n, progress=gr.Progress()):
        """Process resumes and return results."""
        if not resume_folder or not job_description:
            return pd.DataFrame(), "Please provide both resume folder and job description."
        
        try:
            progress(0, desc="Initializing system...")
            
            # Initialize system
            nonlocal system
            system = ResumeScreeningSystem(top_n=int(top_n))
            
            progress(0.2, desc="Processing resumes...")
            results_df = system.screen_resumes(resume_folder, job_description)
            
            progress(0.9, desc="Generating summary...")
            
            # Create summary
            summary = f"""
            ## Resume Screening Summary
            - Total candidates processed: {len(results_df)}
            - Strong Matches: {len(results_df[results_df['Category'] == 'Strong Match'])}
            - Partial Matches: {len(results_df[results_df['Category'] == 'Partial Match'])}
            - Weak Matches: {len(results_df[results_df['Category'] == 'Weak Match'])}
            - Top candidate: {results_df.iloc[0]['Candidate Name'] if not results_df.empty else 'N/A'}
            - Top score: {results_df.iloc[0]['Final Cross-Encoder Score']:.3f} if not results_df.empty else 'N/A'
            
            ### Model Information
            - Sentence-BERT Model: all-MiniLM-L6-v2
            - Cross-Encoder Model: cross-encoder/ms-marco-MiniLM-L-6-v2
            - Top N candidates passed to Cross-Encoder: {system.top_n}
            """
            
            progress(1.0, desc="Complete!")
            
            return results_df, summary
            
        except Exception as e:
            logger.error(f"Error in processing: {e}")
            return pd.DataFrame(), f"Error: {str(e)}"
    
    def save_results(results_df):
        """Save results to CSV."""
        if results_df.empty:
            return "No results to save."
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"resume_screening_results_{timestamp}.csv"
        results_df.to_csv(filename, index=False)
        return f"Results saved to {filename}"
    
    # Create Gradio interface
    with gr.Blocks(title="Resume Screening System", theme=gr.themes.Soft()) as interface:
        gr.Markdown("""
        # 📄 Resume Screening System
        Upload a folder of PDF resumes and a job description to automatically screen and rank candidates.
        """)
        
        with gr.Row():
            with gr.Column(scale=2):
                # Input components
                resume_folder = gr.Textbox(
                    label="Resume Folder Path",
                    placeholder="Enter the path to folder containing PDF resumes",
                    lines=1
                )
                job_description = gr.Textbox(
                    label="Job Description",
                    placeholder="Paste the job description here",
                    lines=10
                )
                top_n = gr.Number(
                    label="Top N Candidates",
                    value=100,
                    minimum=1,
                    maximum=500,
                    step=1
                )
                
                with gr.Row():
                    process_btn = gr.Button("🔍 Screen Resumes", variant="primary")
                    save_btn = gr.Button("💾 Save Results", variant="secondary")
            
            with gr.Column(scale=3):
                # Output components
                results_output = gr.Dataframe(
                    label="Screening Results",
                    interactive=False,
                    headers=["Candidate Name", "Initial Similarity Score", 
                            "Final Cross-Encoder Score", "Category", 
                            "Extracted Keywords", "PDF Path"]
                )
                summary_output = gr.Markdown(label="Summary")
                
        # Status and save message
        save_status = gr.Textbox(label="Save Status", interactive=False)
        
        # Set up event handlers
        process_btn.click(
            fn=process_resumes,
            inputs=[resume_folder, job_description, top_n],
            outputs=[results_output, summary_output]
        )
        
        save_btn.click(
            fn=save_results,
            inputs=[results_output],
            outputs=[save_status]
        )
        
        # Add examples
        gr.Markdown("""
        ### How to use:
        1. Prepare a folder containing PDF resumes
        2. Paste your job description
        3. Click "Screen Resumes" to start the process
        4. Review the ranked results with similarity scores and categories
        5. Click "Save Results" to export to CSV
        
        ### Categorization:
        - **Strong Match**: Cross-Encoder score ≥ 0.7
        - **Partial Match**: Cross-Encoder score 0.4 - 0.7
        - **Weak Match**: Cross-Encoder score < 0.4
        """)
    
    return interface

# Main execution
if __name__ == "__main__":
    # Create and launch the interface
    interface = create_gradio_interface()
    interface.launch(share=False, server_name="0.0.0.0", server_port=7860)