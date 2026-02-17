export default function Footer() {
  const currentYear = new Date().getFullYear();
  return (
    <footer className="bg-secondary border-t border-border">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex justify-between items-center text-sm">
          <p className="text-muted-foreground">&copy; {currentYear} Phoenix Agent. All rights reserved.</p>
          <p className="text-muted-foreground">
            Powered by{" "}
            <a
              href="https://www.anthropic.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-foreground hover:text-phoenix transition-colors"
            >
              Anthropic
            </a>
          </p>
        </div>
      </div>
    </footer>
  );
}
