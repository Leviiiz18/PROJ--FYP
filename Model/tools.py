import logging
from livekit.agents import function_tool, RunContext
import requests
#from langchain_community.tools import DuckDuckGoSearchRun
import os
import asyncio
import aiohttp 
import smtplib
from email.mime.multipart import MIMEMultipart  
from email.mime.text import MIMEText
from typing import Optional

@function_tool()
async def get_weather(
    context: RunContext,  # type: ignore
    city: str) -> str:
    """
    Get the current weather for a given city.
    """
    try:
        response = requests.get(
            f"https://wttr.in/{city}?format=3")
        if response.status_code == 200:
            logging.info(f"Weather for {city}: {response.text.strip()}")
            return response.text.strip()   
        else:
            logging.error(f"Failed to get weather for {city}: {response.status_code}")
            return f"Could not retrieve weather for {city}."
    except Exception as e:
        logging.error(f"Error retrieving weather for {city}: {e}")
        return f"An error occurred while retrieving weather for {city}." 

@function_tool()
async def search_web(query: str) -> str:
    """Perform a web search using Google Custom Search and summarize the top 3 results."""
    GOOGLE_API_KEY = os.getenv("CUSTOM_API_KEY")
    CSE_ID = os.getenv("SEARCH_ENGINE_ID")
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": CSE_ID,
        "q": query
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                data = await resp.json()

                items = data.get("items", [])
                if not items:
                    return "I couldn't find anything relevant."

                response = "Here are the top results:\n"
                for i, item in enumerate(items[:3], start=1):
                    title = item.get("title", "No title")
                    snippet = item.get("snippet", "No description")
                    response += f"\nResult {i}: {title}. {snippet}"

                return response.strip()

    except Exception as e:
        return f"An error occurred while searching: {str(e)}"


@function_tool()    
async def send_email(
    context: RunContext,  # type: ignore
    to_email: str,
    subject: str,
    message: str,
    cc_email: Optional[str] = None
) -> str:
    """
    Send an email through Gmail.
    
    Args:
        to_email: Recipient email address
        subject: Email subject line
        message: Email body content
        cc_email: Optional CC email address
    """
    try:
        # Gmail SMTP configuration
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        
        # Get credentials from environment variables
        gmail_user = os.getenv("GMAIL_USER")
        gmail_password = os.getenv("GMAIL_APP_PASSWORD")  # Use App Password, not regular password
        
        if not gmail_user or not gmail_password:
            logging.error("Gmail credentials not found in environment variables")
            return "Email sending failed: Gmail credentials not configured."
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = gmail_user
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Add CC if provided
        recipients = [to_email]
        if cc_email:
            msg['Cc'] = cc_email
            recipients.append(cc_email)
        
        # Attach message body
        msg.attach(MIMEText(message, 'plain'))
        
        # Connect to Gmail SMTP server
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Enable TLS encryption
        server.login(gmail_user, gmail_password)
        
        # Send email
        text = msg.as_string()
        server.sendmail(gmail_user, recipients, text)
        server.quit()
        
        logging.info(f"Email sent successfully to {to_email}")
        return f"Email sent successfully to {to_email}"
        
    except smtplib.SMTPAuthenticationError:
        logging.error("Gmail authentication failed")
        return "Email sending failed: Authentication error. Please check your Gmail credentials."
    except smtplib.SMTPException as e:
        logging.error(f"SMTP error occurred: {e}")
        return f"Email sending failed: SMTP error - {str(e)}"
        logging.error(f"Error sending email: {e}")
        return f"An error occurred while sending email: {str(e)}"

@function_tool()
async def query_knowledge_base(
    context: RunContext,  # type: ignore
    session_id: str,
    question: str
) -> str:
    """
    Query the student's uploaded textbook (knowledge base) to answer their question.
    ALWAYS use this tool if the student asks a question about their textbook, a story, or a specific topic you don't know the context of.
    """
    try:
        logging.info(f"Querying knowledge base for session {session_id} with question: {question}")
        
        # We query the local rag-query API
        url = "http://localhost:8000/api/rag-query"
        payload = {
            "session_id": session_id,
            "question": question,
            "grade": 3  # Defaulting to 3, but the prompt handles the tone anyway
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logging.error(f"RAG query failed: {resp.status} - {error_text}")
                    return "I'm sorry, I couldn't find the answer in the textbook right now."
                    
                full_answer = ""
                # Parse the SSE stream
                async for line in resp.content:
                    line = line.decode('utf-8').strip()
                    if line.startswith('data: '):
                        data_str = line[6:]
                        if data_str == '[DONE]':
                            break
                        try:
                            import json
                            data = json.loads(data_str)
                            if 'text' in data:
                                full_answer += data['text']
                        except json.JSONDecodeError:
                            continue
                
                return full_answer.strip() if full_answer else "I couldn't find an answer in the textbook."
                
    except Exception as e:
        logging.error(f"Error querying knowledge base: {e}")
        return f"An error occurred while checking the textbook: {str(e)}"