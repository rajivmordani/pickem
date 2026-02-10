#!/usr/bin/env python3
"""NFL Pick'em Web Application - Entry Point"""
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080,
            ssl_context=('cert.pem', 'key.pem'))
