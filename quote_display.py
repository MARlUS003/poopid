import tkinter as tk
import random
import re

QUOTES_FILE = "log/quotes.txt"

DISCORD_USERS = {
    "1271500729537794229": "Niko",
    "279880443200012288": "Seam",
    "483868190498357248": "Deadguana",
    "490921471225626647": "Methmer",
    "602901448778579978": "Niko",
}


def resolve_author(raw):
    raw = raw.strip()
    # Strip trailing notes like "ca. 2 uker siden" or emoji
    raw = re.sub(r'\s+ca\..*$', '', raw).strip()
    raw = re.sub(r'\s+[🔥].*$', '', raw).strip()
    mention = re.match(r'<@!?(\d+)>', raw)
    if mention:
        uid = mention.group(1)
        return DISCORD_USERS.get(uid, uid)
    return raw.lstrip('@').strip()


def parse_quotes(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    entries = raw.split("||ENTRY_SEP||")
    quotes = []

    for entry in entries:
        # Each entry is: [Submitter]\n"quote text"\n— Author
        # The \n characters are literal backslash-n in the file, not real newlines.
        # First, strip the [Submitter] tag and any URL lines from real newlines.
        lines = entry.strip().splitlines()
        content_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if re.search(r'https?://', line):
                continue
            if re.match(r'^\[.+\]$', line):  # skip [Submitter] tags
                continue
            content_lines.append(line)

        if not content_lines:
            continue

        # Rejoin remaining content (should be a single line like: "quote"\n— Author)
        full = ' '.join(content_lines)

        # Split on the literal \n followed by an author marker (—, --, \-, ~~)
        split = re.split(r'\\n\s*(?:—|--|\\-|~~)\s*', full, maxsplit=1)

        if len(split) == 2:
            quote_text = split[0].strip().strip('"').replace('\\n', ' ').strip()
            author = resolve_author(split[1])
        else:
            # No author separator — only keep if it looks like a quoted string
            if full.startswith('"') and full.endswith('"'):
                quote_text = full.strip('"').strip()
                author = None
            else:
                continue

        if quote_text:
            quotes.append((quote_text, author))

    return quotes


def get_random_quote(quotes):
    return random.choice(quotes)


class QuoteApp:
    def __init__(self, root, quotes):
        self.root = root
        self.quotes = quotes

        self.root.title("Quotes")
        self.root.configure(bg="#0d0d0d")
        self.root.attributes("-fullscreen", True)
        self.root.config(cursor="none")
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.bind("<space>", lambda e: self.show_next())
        self.root.bind("<Button-1>", lambda e: self.show_next())

        # Outer frame for centering
        self.frame = tk.Frame(self.root, bg="#0d0d0d")
        self.frame.place(relx=0.5, rely=0.5, anchor="center")

        # Decorative top bar
        self.bar = tk.Frame(self.frame, bg="#e8c547", height=3, width=300)
        self.bar.pack(pady=(0, 20))

        # Quote text
        self.quote_var = tk.StringVar()
        self.quote_label = tk.Label(
            self.frame,
            textvariable=self.quote_var,
            font=("Georgia", 18, "italic"),
            fg="#f0ece0",
            bg="#0d0d0d",
            wraplength=440,
            justify="center",
        )
        self.quote_label.pack(pady=(0, 16))

        # Author
        self.author_var = tk.StringVar()
        self.author_label = tk.Label(
            self.frame,
            textvariable=self.author_var,
            font=("Courier", 14),
            fg="#e8c547",
            bg="#0d0d0d",
        )
        self.author_label.pack()

        # Bottom hint
        self.hint = tk.Label(
            self.root,
            text="tap or press space for next quote",
            font=("Courier", 8),
            fg="#333333",
            bg="#0d0d0d",
        )
        self.hint.place(relx=0.5, rely=0.97, anchor="center")

        self.show_next()

    def show_next(self):
        quote, author = get_random_quote(self.quotes)
        self.quote_var.set(f'"{quote}"')
        if author:
            self.author_label.config(fg="#e8c547")
            self.author_var.set(f"— {author}")
        else:
            self.author_label.config(fg="#555555")
            self.author_var.set("— unknown")
        # Schedule next auto-rotate in 60 seconds
        if hasattr(self, '_timer'):
            self.root.after_cancel(self._timer)
        self._timer = self.root.after(60000, self.show_next)


def main():
    quotes = parse_quotes(QUOTES_FILE)
    if not quotes:
        print("No quotes found!")
        return

    root = tk.Tk()
    app = QuoteApp(root, quotes)
    root.mainloop()


if __name__ == "__main__":
    main()
