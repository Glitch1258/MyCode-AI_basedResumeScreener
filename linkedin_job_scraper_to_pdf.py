import os
import re
import time
import random
from jobspy import scrape_jobs
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

OUTPUT_DIR = "output_pdfs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def sanitize_filename(name):
    """Clean job title/company for safe file naming."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()[:50]

def create_pdf(job_title, company, location, job_url, description, file_path):
    """Generate a clean PDF report for a job listing using ReportLab."""
    doc = SimpleDocTemplate(
        file_path,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'JobTitle',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        spaceAfter=10
    )
    
    meta_style = ParagraphStyle(
        'MetaInfo',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor='#555555',
        spaceAfter=15
    )
    
    body_style = ParagraphStyle(
        'Description',
        parent=styles['BodyText'],
        fontSize=10,
        leading=14,
        spaceAfter=10
    )

    story = [
        Paragraph(job_title or "Job Title Not Provided", title_style),
        Paragraph(f"<b>Company:</b> {company or 'N/A'} | <b>Location:</b> {location or 'N/A'}", meta_style),
        Paragraph(f"<b>Job Link:</b> {job_url or 'N/A'}", meta_style),
        Spacer(1, 10),
        Paragraph("<b>Job Description & Requirements:</b>", styles['Heading2']),
        Spacer(1, 5)
    ]

    # Convert line breaks to HTML breaks for ReportLab
    formatted_desc = str(description).replace('\n', '<br/>') if description else "No description available."
    story.append(Paragraph(formatted_desc, body_style))

    try:
        doc.build(story)
        return True
    except Exception as e:
        print(f"Error generating PDF for {job_title}: {e}")
        return False

def scrape_and_export_pdfs(search_term, location, total_jobs=10, batch_size=3):
    """Scrapes jobs in tiny batches with long delays to minimize 429 rate-limiting."""
    print(f"Starting job search for '{search_term}' in '{location}'...\n")
    
    total_scraped = 0
    pdf_count = 0

    while total_scraped < total_jobs:
        current_batch = min(batch_size, total_jobs - total_scraped)
        print(f"Fetching batch of {current_batch} jobs...")

        try:
            jobs = scrape_jobs(
                site_name=["linkedin"],
                search_term=search_term,
                location=location,
                results_wanted=current_batch,
                hours_old=72,
                fetch_description=True,
                verbose=0
            )
            
            if jobs.empty:
                print("No more jobs found.")
                break

            for _, row in jobs.iterrows():
                title = str(row.get('title', 'Unknown Title'))
                company = str(row.get('company', 'Unknown Company'))
                job_loc = str(row.get('location', 'N/A'))
                url = str(row.get('job_url', 'N/A'))
                desc = row.get('description', 'No description found.')

                # Unique timestamp + job title + company
                filename = f"{sanitize_filename(company)}_{sanitize_filename(title)}_{int(time.time())}.pdf"
                filepath = os.path.join(OUTPUT_DIR, filename)

                if create_pdf(title, company, job_loc, url, desc, filepath):
                    pdf_count += 1
                    print(f"Saved PDF: {filename}")

            total_scraped += len(jobs)

        except Exception as e:
            print(f"Scraping error: {e}")
            break

        if total_scraped < total_jobs:
            # Long randomized delay (20 to 35 seconds) to avoid HTTP 429
            wait_time = random.uniform(20, 35)
            print(f"Pacing request: waiting {wait_time:.1f} seconds before next batch...\n")
            time.sleep(wait_time)

    print(f"\nCompleted! Total PDFs generated: {pdf_count}")

if __name__ == "__main__":
    # Targeted Software Engineering search query
    QUERY = '"DotNet Developer"'
    LOCATION = "Remote"
    TOTAL_JOBS_TO_FETCH = 50  # Kept small to prevent immediate blocks

    scrape_and_export_pdfs(QUERY, LOCATION, total_jobs=TOTAL_JOBS_TO_FETCH, batch_size=2)
