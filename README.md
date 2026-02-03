# ✨ Text Summarizer

A modern, AI-powered web application that transforms long texts into concise summaries using advanced Natural Language Processing (NLP) techniques.

## 🌟 Features

- **Smart Summarization**: Uses extractive summarization based on word frequency and sentence scoring
- **Adjustable Summary Length**: Control summary ratio from 10% to 90% of original text
- **Real-time Statistics**: Track word count, character count, and sentence count as you type
- **Modern UI**: Beautiful, responsive design with smooth animations
- **Dark Mode**: Toggle between light and dark themes for comfortable viewing
- **Copy & Download**: Easily copy summaries to clipboard or download as text files
- **Example Text**: Load sample text to try the summarizer instantly
- **Keyboard Shortcuts**: 
  - `Ctrl/Cmd + Enter`: Submit form
  - `D`: Toggle dark mode
  - `Escape`: Clear text (when focused on textarea)
- **Input Validation**: Comprehensive validation with helpful error messages
- **Accessibility**: ARIA labels and keyboard navigation support
- **API Endpoint**: RESTful API for programmatic access

## 🚀 Quick Start

### Prerequisites

- Python 3.7 or higher
- pip (Python package manager)

### Installation

1. Clone or download this repository:
```bash
cd TextSummarizer
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

4. Open your browser and navigate to:
```
http://localhost:5001
```

## 📖 Usage

### Web Interface

1. **Enter Text**: Paste or type your text in the textarea
2. **Adjust Length**: Use the slider to set your desired summary length (10%-90%)
3. **Summarize**: Click the "Summarize" button or press `Ctrl/Cmd + Enter`
4. **Copy/Download**: Use the action buttons to copy or download your summary

### API Usage

The application provides a RESTful API endpoint for programmatic access:

**Endpoint**: `POST /api/summarize`

**Request Body**:
```json
{
    "text": "Your text to summarize here...",
    "ratio": 0.3
}
```

**Response**:
```json
{
    "summary": "Generated summary text...",
    "stats": {
        "original_words": 150,
        "original_chars": 850,
        "summary_words": 45,
        "summary_chars": 255,
        "compression_ratio": 70.0
    }
}
```

**Example using curl**:
```bash
curl -X POST http://localhost:5001/api/summarize \
  -H "Content-Type: application/json" \
  -d '{"text": "Your text here...", "ratio": 0.3}'
```

## 🔧 Configuration

### Text Limits

- **Minimum Length**: 10 characters
- **Maximum Length**: 100,000 characters
- **Maximum File Size**: 16MB

### Port Configuration

By default, the app runs on port 5001. To change this, edit `app.py`:

```python
app.run(debug=True, host='0.0.0.0', port=YOUR_PORT)
```

## 🏗️ Project Structure

```
TextSummarizer/
├── app.py              # Flask application and routes
├── summarizer.py       # Core summarization logic
├── templates/
│   └── index.html     # Frontend HTML template
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## 🧠 How It Works

The summarizer uses an extractive approach:

1. **Tokenization**: Breaks text into sentences and words
2. **Word Frequency**: Calculates frequency of important words (excluding stopwords)
3. **Sentence Scoring**: Scores sentences based on word frequency
4. **Selection**: Selects top-scoring sentences based on the specified ratio
5. **Ordering**: Maintains original sentence order in the summary

## 🛠️ Technologies Used

- **Backend**: Flask (Python web framework)
- **NLP**: NLTK (Natural Language Toolkit)
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **Styling**: Modern CSS with gradients and animations

## 📝 License

This project is open source and available for personal and educational use.

## 🤝 Contributing

Contributions are welcome! Feel free to submit issues or pull requests.

## ⚠️ Notes

- The application downloads NLTK data on first run (punkt tokenizer and stopwords)
- For production use, consider:
  - Disabling debug mode
  - Adding CSRF protection
  - Implementing rate limiting
  - Using a production WSGI server (e.g., Gunicorn)

## 🐛 Troubleshooting

**Port already in use**: Change the port in `app.py` or stop the process using port 5001

**NLTK download issues**: Ensure you have internet connection for first-time setup

**Import errors**: Make sure all dependencies are installed: `pip install -r requirements.txt`

## 📧 Support

For issues or questions, please open an issue on the repository.

---

Made with ❤️ using Flask and NLTK
