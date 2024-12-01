import os
import streamlit as st
from groq import Groq
import pdfplumber
from pptx import Presentation
import pandas as pd
from docx import Document
import time
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

# Streamlit configuration
st.set_page_config(
    page_title="Exam Paper Generator",
    page_icon="📝",
    layout="wide"
)

# PDF generation function
def generate_styled_pdf(title: str, content: str) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor("#2C3E50"),
        alignment=1
    )
    normal_style = styles['BodyText']

    elements = [
        Paragraph(title, title_style),
        Spacer(1, 0.3 * inch),
        Paragraph(content.replace("\n", "<br />"), normal_style)
    ]

    doc.build(elements)
    buffer.seek(0)
    return buffer

# Document processor class
class DocumentProcessor:
    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)

    def extract_text(self, file) -> str:
        """Extract text from different document types."""
        try:
            if file.type == "application/pdf":
                with pdfplumber.open(file) as pdf:
                    return "\n".join(page.extract_text() or "" for page in pdf.pages)
            elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                doc = Document(file)
                return "\n".join(paragraph.text for paragraph in doc.paragraphs)
            elif file.type == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
                ppt = Presentation(file)
                return "\n".join(
                    shape.text for slide in ppt.slides for shape in slide.shapes if hasattr(shape, "text")
                )
            elif file.type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
                df = pd.read_excel(file)
                return df.to_string(index=False)
            elif file.type == "text/plain":
                return file.getvalue().decode("utf-8")
            else:
                return "Unsupported file format"
        except Exception as e:
            return f"Error processing file: {str(e)}"

    def generate_questions(self, content: str, question_type: str, num_questions: int, difficulty: str, specific_topic: str = None) -> str:
        """Generate questions based on content."""
        if not content or content.strip() == "":
            return "No content provided for question generation."

        prompt = f"""
        Generate {num_questions} {question_type} questions {'on the topic of ' + specific_topic if specific_topic else ''} 
        based on the following content.
        Difficulty level: {difficulty}.
        
        Content:
        {content[:5000]}  # Limit content to prevent overwhelming the API

        Format:
        - For MCQs:
          Q[number]. [Question]
          A) Option 1 \n
          B) Option 2 \n
          C) Option 3 \n
          D) Option 4 \n
        - For short questions: Q[number]. [Question]
        - For long questions: Q[number]. [Detailed Question]
        proper line spacind after each question and option and give everthind in proper format and dont give ram data or headings
        """
        try:
            response = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt }],
                model="gemma2-9b-it"
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating questions: {str(e)}"

# Main application function
def main():
    st.title("📝 Exam Paper Generator")
    st.write("Upload your documents to generate an exam paper with customized questions.")

    # API Key Management
    api_key =os.getenv("GROQ_API_KEY", "")


    # File uploader
    uploaded_files = st.file_uploader(
        "📎 Upload Documents",
        type=["pdf", "pptx", "docx", "xlsx", "txt"],
        accept_multiple_files=True
    )

    # Topic input
    specific_topic = st.text_input("🎯 Specify a Specific Topic (Optional)", 
                                   help="Enter a topic to focus the exam questions. Leave blank to use entire document content.")

    # Proceed only if files are uploaded
    if uploaded_files:
        try:
            # Initialize processor
            processor = DocumentProcessor(api_key)

            # Extract content from uploaded files
            combined_text = "\n\n".join(processor.extract_text(file) for file in uploaded_files)
            
            if not combined_text or combined_text.strip() == "":
                st.error("No text could be extracted from the uploaded documents.")
                return

            st.success("Documents uploaded and processed successfully!")

            # Question type selection
            st.write("### Select Question Types")
            mcq_selected = st.checkbox("Multiple Choice Questions (MCQs)")
            short_selected = st.checkbox("Short Questions")
            long_selected = st.checkbox("Long Questions")

            # Customize question generation
            question_settings = {}
            if mcq_selected:
                st.subheader("Settings for MCQs")
                num_mcqs = st.slider("Number of MCQs:", 1, 20, 5, key="num_mcqs")
                difficulty_mcqs = st.selectbox("Difficulty Level for MCQs:", ["Easy", "Medium", "Hard", "Mixed"], key="diff_mcqs")
                question_settings["mcq"] = {"num_questions": num_mcqs, "difficulty": difficulty_mcqs}

            if short_selected:
                st.subheader("Settings for Short Questions")
                num_short = st.slider("Number of Short Questions:", 1, 20, 5, key="num_short")
                difficulty_short = st.selectbox("Difficulty Level for Short Questions:", ["Easy", "Medium", "Hard", "Mixed"], key="diff_short")
                question_settings["short"] = {"num_questions": num_short, "difficulty": difficulty_short}

            if long_selected:
                st.subheader("Settings for Long Questions")
                num_long = st.slider("Number of Long Questions:", 1, 20, 5, key="num_long")
                difficulty_long = st.selectbox("Difficulty Level for Long Questions:", ["Easy", "Medium", "Hard", "Mixed"], key="diff_long")
                question_settings["long"] = {"num_questions": num_long, "difficulty": difficulty_long}

            # Generate and display questions
            if st.button("🚀 Generate Exam Paper"):
                if not question_settings:
                    st.warning("Please select at least one question type.")
                    return

                with st.spinner("Generating exam paper..."):
                    paper_content = []

                    # Generate questions for each selected type
                    for q_type, settings in question_settings.items():
                        question_type_name = {"mcq": "Multiple Choice Questions", "short": "Short Questions", "long": "Long Questions"}
                        questions = processor.generate_questions(
                            content=combined_text,
                            question_type=question_type_name[q_type].lower(),
                            num_questions=settings["num_questions"],
                            difficulty=settings["difficulty"],
                            specific_topic=specific_topic
                        )
                        paper_content.append(f"### {question_type_name[q_type]}\n\n{questions}")

                    # Combine all generated questions
                    combined_paper = "\n\n".join(paper_content)

                    # Display the generated questions
                    st.write("### Generated Exam Paper")
                    st.write(combined_paper)

                    # Provide download option
                    pdf_buffer = generate_styled_pdf("Exam Paper", combined_paper)
                    st.download_button(
                        label="📥 Download Paper as PDF",
                        data=pdf_buffer,
                        file_name="exam_paper.pdf",
                        mime="application/pdf"
                    )
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
