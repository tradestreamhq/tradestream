#!/bin/sh
# Start script for the Signal Dashboard container.
# Copies static files to nginx html directory and starts nginx.
cp /services/signal_dashboard/nginx.conf /etc/nginx/nginx.conf
cp /services/signal_dashboard/*.html /usr/share/nginx/html/
nginx -g 'daemon off;'
