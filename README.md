# Holiday Offers Scraper

## Overview
This project is a web scraper and email notification system that aggregates holiday offers from various websites, including:

- **Fly4Free**
- **LastMinuter**
- **Wakacyjni Piraci**

The scraper extracts offers from these sources, generates an HTML report, and optionally sends the report via email.

---

## Table of Contents
- [Features](#features)
- [Setup Instructions](#setup-instructions)
- [How to Use](#how-to-use)
- [Development Guide](#development-guide)
  - [Folder Structure](#folder-structure)
  - [Adding New Sources](#adding-new-sources)
  - [Logs](#logs)
- [Contributing](#contributing)
- [License](#license)

---

## Features
- **Web Scraping**: Extracts data from holiday deal websites.
- **HTML Report**: Generates a visually appealing HTML summary of offers.
- **Email Notifications**: Sends the generated report to a specified email address.
- **Caching**: Prevents duplicate processing of previously seen offers.
- **Cross-Platform Support**: Works on Linux and Windows (requires Chrome or Edge browser).

---

## Setup Instructions

### Prerequisites
1. **Python 3.9+**
2. **Google Chrome or Microsoft Edge** installed.
3. **Chromedriver** (Linux: `/usr/bin/chromedriver` assumed, configure as needed).
4. **Pipenv** or virtual environment for dependency management.
5. Environment file (`.env`) with the following keys:
   ```env
   SRC_MAIL=your_email@example.com
   SRC_PWD=your_email_password
   DST_MAIL=recipient_email@example.com
   ```

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/holiday-offers-scraper.git
   cd holiday-offers-scraper
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Verify ChromeDriver installation:
   ```bash
   chromedriver --version
   ```

4. Set up the `.env` file with your email credentials.

5. Run the program:
   ```bash
   python main.py
   ```

---

## How to Use

### Running the Scraper
The scraper can be run directly from the command line:
```bash
python main.py
```

### Scheduled Runs
By default, the scraper is scheduled to run daily at 12:00 PM. You can modify this schedule in the `main.py` file using the [Schedule library](https://schedule.readthedocs.io/).

---

## Development Guide

### Folder Structure
```plaintext
project-root
├── fly_4_free/         # Fly4Free scraper logic
├── lastminuter/        # LastMinuter scraper logic
├── wakacyjni_piraci/   # Wakacyjni Piraci scraper logic
├── templates/          # HTML templates for the report
├── offer.py            # Dataclass for offer representation
├── scrapper_base.py    # Base scraper functionality
├── main.py             # Entry point of the application
└── requirements.txt    # Python dependencies
```

### Adding New Sources
1. Create a new scraper class in a separate folder (e.g., `new_source/`).
2. Inherit from `ScrapperBase` to utilize shared caching and utilities.
3. Implement the `get_offers(driver: webdriver.Chrome) -> list[Offer]` method.
4. Add the new scraper in `main.py`:
   ```python
   new_source_offers = NewSource().get_offers(driver)
   offers.extend(new_source_offers)
   ```

### Logs
- Logs are stored in the console and include detailed debug information for development.
- Format:
  ```plaintext
  YYYY-MM-DD HH:MM:SS - LEVEL - Line: <line_number> - <filename> - <function>() - <message>
  ```

---

## Contributing

Contributions are welcome! To contribute:
1. Fork the repository.
2. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature
   ```
3. Commit your changes:
   ```bash
   git commit -m "Add your feature"
   ```
4. Push to your branch:
   ```bash
   git push origin feature/your-feature
   ```
5. Open a Pull Request.

---

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

