from app import create_app

app = create_app()

if __name__ == '__main__':
    # debug=True but use_reloader=False to eliminate inotify file-system spam
    app.run(debug=True, use_reloader=False)