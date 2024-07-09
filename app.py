from flask import Flask, render_template, redirect, url_for, request, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, func
from datetime import datetime, timedelta
import os
from werkzeug.utils import secure_filename
import fitz

app = Flask(__name__)
app.secret_key = "itissecret"
app.config["SQLALCHEMY_DATABASE_URI"] = 'sqlite:///data.sqlite3'
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

UPLOAD_FOLDER = 'static/uploads/'
COVER_FOLDER = 'static/uploads/cover/'
ALLOWED_EXTENSIONS = {'pdf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['COVER_FOLDER'] = COVER_FOLDER

def allowed_file(filename):
	return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_cover_page(pdf_path, output_path):
	pdf_document = fitz.open(pdf_path)
	first_page = pdf_document[0]
	pix = first_page.get_pixmap()
	pix.save(output_path)
	pdf_document.close()


class Librarian(db.Model):
	_id = db.Column("id", db.Integer, primary_key = True)
	username = db.Column("username", db.String(50), unique = True, nullable = False)
	password = db.Column("password", db.String(100), nullable = False)

	def __init__(self, username, password):
		self.username = username
		self.password = password

class User(db.Model):
	_id = db.Column("id", db.Integer, primary_key = True)
	username = db.Column("username", db.String(50), unique = True, nullable = False)
	password = db.Column("password", db.String(100), nullable = False)

	def __init__(self, username, password):
		self.username = username
		self.password = password

class Section(db.Model):
	_id = db.Column("id", db.Integer, primary_key=True)
	name = db.Column(db.String(100), unique=True, nullable=False)
	date_created = db.Column(db.DateTime, default=datetime.utcnow)
	description = db.Column(db.Text, nullable=True)

	def __init__(self, name, description=None):
		self.name = name
		self.description = description

class Book(db.Model):
	_id = db.Column("id", db.Integer, primary_key=True)
	title = db.Column("title", db.String(100), nullable=False)
	author = db.Column("author", db.String(255), nullable=False)
	date_added = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
	description = db.Column("description", db.Text, nullable=True)
	file_path = db.Column(db.String(255), nullable=False)
	cover_path = db.Column(db.String(255), nullable=False)
	section_id = db.Column(db.Integer, db.ForeignKey('section.id'))
	rating = db.Column(db.Float, nullable=False, default=0.0)

	section = db.relationship('Section', backref=db.backref('book', lazy=True))

	def __init__(self, title, author, description, file_path, cover_path, section_id):
		self.title = title
		self.author = author
		self.description = description
		self.file_path = file_path
		self.cover_path = cover_path
		self.section_id = section_id

class BookRequest(db.Model):
	_id = db.Column("id", db.Integer, primary_key=True)
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
	book_id = db.Column(db.Integer, db.ForeignKey('book.id'))
	timestamp = db.Column(db.DateTime, default=datetime.utcnow)

	user = db.relationship('User', backref=db.backref('book_request', lazy=True))
	book = db.relationship('Book', backref=db.backref('book_request', lazy=True))

	def __init__(self, user_id, book_id):
		self.user_id = user_id
		self.book_id = book_id

class IssuedBook(db.Model):
	_id = db.Column("id", db.Integer, primary_key=True)
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
	book_id = db.Column(db.Integer, db.ForeignKey('book.id'))
	issue_date = db.Column(db.DateTime, default = datetime.utcnow)
	expiry_date = db.Column(db.DateTime)

	user = db.relationship('User', backref=db.backref('issued_book', lazy=True))
	book = db.relationship('Book', backref=db.backref('issued_book', lazy=True))

	def __init__(self, user_id, book_id):
		self.user_id = user_id
		self.book_id = book_id
		self.expiry_date = datetime.utcnow() + timedelta(days = 7)

class BookFeedback(db.Model):
	_id = db.Column("id", db.Integer, primary_key=True)
	book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
	rating = db.Column(db.Integer, nullable=False)
	feedback = db.Column(db.Text, nullable=True)
	date_reviewed = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

	book = db.relationship('Book', backref=db.backref('feedback', lazy=True))
	user = db.relationship('User', backref=db.backref('feedback', lazy=True))

	def __init__(self, book_id, user_id, rating, feedback=None):
		self.book_id = book_id
		self.user_id = user_id
		self.rating = rating
		self.feedback = feedback


@app.route("/")
@app.route("/home")
def home():
	return render_template("index.html")


@app.route("/sign-up", methods = ["POST", "GET"])
def sign_up():
	if request.method == "POST":
		username = request.form["username"]
		password = request.form["password"]

		new_user = User(username, password)

		db.session.add(new_user)
		db.session.commit()

		flash("Account created successfully! You can now login.", "success")
		return redirect(url_for("login"))
	elif "user_id" in session:
		flash("Already logged in!", "warning")
		return redirect(url_for("dashboard"))

	return render_template("sign_up.html")

@app.route("/login", methods = ["POST", "GET"])
def login():
	if request.method == "POST":
		username = request.form["username"]
		password = request.form["password"]

		user = User.query.filter_by(username = username).first()

		if user and user.password == password:
			session["user_id"] = user._id
			flash("Logged in successfully", "success")
			return redirect(url_for("dashboard"))
		else:
			flash("Incorrect username or password. Please try again.", "warning")
	elif "user_id" in session:
		flash("Already logged in!", "warning")
		return redirect(url_for("dashboard"))
	return render_template("login.html")

@app.route("/dashboard")
def dashboard():
	if "user_id" in session:
		user_id = session["user_id"]
		books = Book.query.order_by(Book.date_added.desc()).all()
		sections = Section.query.all()
		requests = BookRequest.query.filter_by(user_id = user_id).order_by(BookRequest.timestamp.desc()).all()
		# issued_books = IssuedBook.query.filter(IssuedBook.user_id == user_id, IssuedBook.expiry_date > datetime.utcnow()).all()
		issued_books = IssuedBook.query.filter_by(user_id = user_id).all()

		valid_issued_books = []
		for issued_book in issued_books:
			if issued_book.expiry_date > datetime.utcnow():
				valid_issued_books.append(issued_book)
			else:
				db.session.delete(issued_book)
				db.session.commit()

		return render_template("dashboard.html", user_id = user_id, books = books, sections = sections, requests = requests, issued_books = valid_issued_books)
	flash("You need to login to view Dashboard!", "warning")
	return redirect(url_for("login"))

@app.route("/request-book", methods=["POST"])
def request_book():
	if "user_id" in session:
		book_id = request.form.get("book_id")
		existing_request = BookRequest.query.filter_by(user_id=session["user_id"], book_id=book_id).first()
		issued_book = IssuedBook.query.filter_by(user_id=session["user_id"], book_id=book_id).first()
		er = BookRequest.query.filter_by(user_id=session["user_id"]).count()
		ib = IssuedBook.query.filter_by(user_id=session["user_id"]).count()

		if not Book.query.filter_by(_id=book_id).first():
			flash("Book doesn't exist!", "warning")
		elif existing_request:
			flash("You have already requested this book.", "warning")
		elif issued_book:
			flash("You already have this book", "warning")
		elif not er + ib < 5:
			flash("You cannot request more than 5 books", "warning")
		else:
			new_request = BookRequest(user_id=session["user_id"], book_id=book_id)
			db.session.add(new_request)
			db.session.commit()

			flash("Book request submitted successfully!", "success")
		return redirect(url_for("dashboard"))
	else:
		flash("You need to login to request a book!", "warning")
		return redirect(url_for("login"))

@app.route("/cancel-request", methods=["POST"])
def cancel_request():
	if "user_id" in session:
		request_id = request.form.get("request_id")
		br = BookRequest.query.get(request_id)
		if not br:
			flash("There is no such pending request!", "warning")
		else:
			db.session.delete(br)
			db.session.commit()
			flash("Book request cancelled!", "success")
		return redirect(url_for("dashboard"))
	flash("You need to login to cancel a request!", "warning")
	return redirect(url_for("login"))

@app.route("/read-book", methods=["POST"])
def read_book():
	if "user_id" in session:
		book_id = request.form.get("book_id")
		issued_book = IssuedBook.query.filter_by(user_id=session["user_id"], book_id=book_id).first()

		if issued_book:
			if issued_book.expiry_date > datetime.utcnow():
				b = Book.query.filter_by(_id=book_id).first()
				return render_template("read_book.html", book=b)
			else:
				flash("The due date for this book has passed. It has been automatically returned.", "warning")
				return redirect(url_for("dashboard"))
		else:
			flash("You haven't borrowed this book", "warning")
			return redirect(url_for("dashboard"))
	else:
		flash("You need to login to read a book!", "warning")
		return redirect(url_for("login"))

@app.route("/return-book", methods=["POST"])
def return_book():
	if "user_id" in session:
		book_id = request.form.get("book_id")
		issued_book = IssuedBook.query.filter_by(user_id=session["user_id"], book_id=book_id).first()

		if issued_book:
			db.session.delete(issued_book)
			db.session.commit()
			flash("Book returned successfully", "success")
		else:
			flash("You haven't borrowed this book", "warning")

		return redirect(url_for("dashboard"))
	else:
		flash("You need to login to return a book!", "warning")
		return redirect(url_for("login"))

@app.route("/review-book", methods=["POST"])
def review_book():
	if "user_id" in session:
		user_id = session["user_id"]
		book_id = request.form["book_id"]
		issued_book = IssuedBook.query.filter_by(user_id = user_id, book_id = book_id).first()
		if issued_book and issued_book.expiry_date > datetime.utcnow():
			b = Book.query.filter_by(_id=book_id).first()
			f = BookFeedback.query.filter_by(user_id=user_id, book_id=book_id).first()
			return render_template("review_book.html", book = b, user_feedback=f)
		else:
			flash("You need to issue the book before reviewing it", "warning")
			return redirect(url_for("dashboard"))
	else:
		flash("You need to login to review a book!", "warning")
		return redirect(url_for("login"))

@app.route("/submit-feedback", methods=["POST"])
def submit_feedback():
	if "user_id" in session:
		user_id = session["user_id"]
		book_id = request.form.get("book_id")
		rating = int(request.form.get("rating"))
		feedback = request.form.get("feedback")

		existing_feedback = BookFeedback.query.filter_by(book_id=book_id, user_id=user_id).first()
		if existing_feedback:
			flash("You have already submitted feedback for this book.", "warning")
		else:
			new_feedback = BookFeedback(book_id=book_id, user_id=user_id, rating=rating, feedback=feedback)
			db.session.add(new_feedback)
			db.session.commit()

			b = Book.query.filter_by(_id = book_id).first()
			avg_rating = db.session.query(func.avg(BookFeedback.rating)).filter_by(book_id=book_id).scalar()
			b.rating = avg_rating
			db.session.commit()
			flash("Feedback submitted successfully!", "success")
		return redirect(url_for("dashboard"))
	else:
		flash("You need to login to submit feedback!", "warning")
		return redirect(url_for("login"))

@app.route("/update-feedback", methods=["POST"])
def update_feedback():
	if "user_id" in session:
		user_id = session["user_id"]
		book_id = request.form.get("book_id")
		rating = int(request.form.get("rating"))
		feedback = request.form.get("feedback")

		existing_feedback = BookFeedback.query.filter_by(book_id=book_id, user_id=user_id).first()
		if existing_feedback:
			existing_feedback.rating = rating
			existing_feedback.feedback = feedback
			db.session.commit()

			b = Book.query.filter_by(_id = book_id).first()
			avg_rating = db.session.query(func.avg(BookFeedback.rating)).filter_by(book_id=book_id).scalar()
			b.rating = avg_rating
			db.session.commit()
			flash("Feedback updated successfully!", "success")
		else:
			flash("No existing feedback to update!", "warning")
		return redirect(url_for("dashboard"))
	else:
		flash("You need to login to update feedback!", "warning")
		return redirect(url_for("login"))

@app.route("/view-section/<int:section_id>")
def section_books_user(section_id):
	if "user_id" in session:
		section = Section.query.get(section_id)
		books = Book.query.filter_by(section_id=section_id).all()
		return render_template("section_books_user.html", section = section, books = books)
	flash("You need to login to view sections!", "warning")
	return redirect(url_for("librarian_login"))

@app.route("/search", methods=["GET"])
def search():
	if "user_id" in session:
		query = request.args.get("query")
		search_type = request.args.get("search_type")
		
		if not query:
			flash("Please enter a search query.", "warning")
			return redirect(url_for("dashboard"))

		if search_type == "books":
			books = Book.query.outerjoin(Section).filter(or_(Book.title.ilike(f"%{query}%"), 
				Book.author.ilike(f"%{query}%"), Section.name.ilike(f"%{query}%"))).all()
			return render_template("search_results_books.html", books=books, query=query)
		elif search_type == "sections":
			sections = Section.query.filter(Section.name.ilike(f"%{query}%")).all()
			return render_template("search_results_sections.html", sections=sections, query=query)
		else:
			flash("Invalid search type selected.", "warning")
			return redirect(url_for("dashboard"))
		
	flash("You need to login to search for books!", "warning")
	return redirect(url_for("login"))

@app.route("/logout")
def logout():
	if "user_id" not in session:
		flash("You were not logged in!", "warning")
	else:
		flash("You have been logged out!", "success")
	session.pop("user_id", None)
	return redirect(url_for("login"))


@app.route("/librarian-login", methods = ["POST", "GET"])
def librarian_login():
	if request.method == "POST":
		username = request.form["username"]
		password = request.form["password"]

		lib = Librarian.query.filter_by(username = username).first()

		if lib and lib.password == password:
			session["lib_id"] = lib._id
			flash("Logged in successfully", "success")
			return redirect(url_for("librarian"))
		else:
			flash("Incorrect username or password. Please try again.", "warning")
	elif "lib_id" in session:
		flash("Already logged in!", "warning")
		return redirect(url_for("librarian"))
	return render_template("librarian_login.html")

@app.route("/librarian")
def librarian():
	if "lib_id" in session:
		lib_id = session["lib_id"]
		sections = Section.query.all()
		books = Book.query.all()
		users = User.query.all()
		ubs = Book.query.filter_by(section_id="").all()
		requests = BookRequest.query.order_by(BookRequest.timestamp.desc()).all()
		return render_template("librarian_dashboard.html", lib_id = lib_id, sections = sections, books = books, users = users, requests = requests, ubs=ubs)
	flash("You need to login to view Librarian Dashboard!", "warning")
	return redirect(url_for("librarian_login"))

@app.route("/add-section", methods = ["POST", "GET"])
def add_sections():
	if request.method == "POST":
		name = request.form["name"]
		description = request.form["description"]
		sec = Section.query.filter_by(name = name).first()

		if sec:
			flash("Section already present", "warning")
			return redirect(url_for("librarian"))
		else:
			new_section = Section(name=name, description=description)
			db.session.add(new_section)
			db.session.commit()
			flash("Section added successfully", "success")
			return redirect(url_for("librarian"))

	elif "lib_id" in session:
		return render_template("add_sections.html")
	else:
		flash("You need to login as librarian to add Sections!", "warning")
		return redirect(url_for("librarian_login"))

@app.route("/edit-section/<int:section_id>", methods=["GET", "POST"])
def edit_section(section_id):
	section = Section.query.get(section_id)

	if request.method == "POST":
		section.name = request.form["name"]
		section.description = request.form["description"]
		db.session.commit()
		flash("Section updated successfully", "success")
		return redirect(url_for("librarian"))

	elif "lib_id" in session:
		return render_template("edit_section.html", section=section)

	else:
		flash("You need to login as librarian to edit Sections!", "warning")
		return redirect(url_for("librarian_login"))

@app.route("/delete-section", methods=["POST"])
def delete_section():
	if "lib_id" in session:
		section_id = request.form.get("section_id")
		section = Section.query.get(section_id)

		if section:
			books_in_section = Book.query.filter_by(section_id=section_id).all()
			for book in books_in_section:
				book.section_id = None
				# db.session.delete(book)
			db.session.delete(section)
			db.session.commit()
			flash("Section deleted successfully", "success")
		else:
			flash("Section not found", "danger")

		return redirect(url_for("librarian"))
	else:
		flash("You need to login as librarian to delete sections!", "warning")
		return redirect(url_for("librarian_login"))

@app.route("/section/<int:section_id>")
def section_books_librarian(section_id):
	if "lib_id" in session:
		section = Section.query.get(section_id)
		books = Book.query.filter_by(section_id=section_id).all()
		return render_template("section_books_librarian.html", section = section, books = books)
	flash("You need to login as librarian to view sections!", "warning")
	return redirect(url_for("librarian_login"))

@app.route("/add-book-to-section", methods=["POST"])
def add_book_to_section():
	if "lib_id" in session:
		if request.method == "POST":
			book_ids = request.form.getlist("book_ids")
			section_id = request.form.get("section_id")

			book_ids = [int(i) for i in book_ids]

			if not section_id:
				flash("Please select a section.", "warning")
				return redirect(url_for("librarian"))

			books = Book.query.filter(Book._id.in_(book_ids)).all()

			for book in books:
				if not book.section_id:
					book.section_id = section_id		

			db.session.commit()
			flash("Books added to section successfully.", "success")
			return redirect(url_for("librarian"))
		else:
			flash("Invalid request method.", "danger")
			return redirect(url_for("librarian"))
	else:
		flash("You need to login as librarian to add books to sections!", "warning")
		return redirect(url_for("librarian_login"))

@app.route("/add-book", methods=["POST", "GET"])
def add_book():
	if request.method == "POST":
		title = request.form["title"]
		author = request.form["author"]
		description = request.form["description"]
		section_id = request.form["section"]

		if 'book_file' not in request.files:
			flash('No file part', 'danger')
			return redirect(request.url)

		file = request.files['book_file']

		if file.filename == '':
			flash('No selected file', 'danger')
			return redirect(request.url)

		if file and allowed_file(file.filename):
			filename = secure_filename(file.filename)
			file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
			file.save(file_path)

			cover_path = os.path.join(app.config['COVER_FOLDER'], filename.rsplit('.', 1)[0]+'.png')
			extract_cover_page(file_path, cover_path)

			new_book = Book(title=title, author=author, description=description, file_path=file_path, cover_path=cover_path, section_id=section_id)
			db.session.add(new_book)
			db.session.commit()
			flash('Book added successfully', 'success')
			return redirect(url_for('librarian'))

		flash('Invalid file format. Only PDF files are allowed', 'danger')
		return redirect(request.url)

	elif "lib_id" in session:
		section_id = request.args.get("section_id")
		if section_id:
			section_id = int(section_id)
		sections = Section.query.all()
		return render_template("add_book.html", sections=sections, section_id=section_id)

	flash("You need to login as librarian to add books!", "warning")
	return redirect(url_for("librarian_login"))

@app.route("/edit-book/<int:book_id>", methods=["GET", "POST"])
def edit_book(book_id):
	if request.method == "POST":
		book = Book.query.get(book_id)
		
		book.title = request.form["title"]
		book.author = request.form["author"]
		book.description = request.form["description"]
		book.section_id = request.form["section"]
		db.session.commit()

		flash("Book details updated successfully", "success")
		return redirect(url_for("book_details", book_id=book_id))

	elif "lib_id" in session:
		book = Book.query.get(book_id)
		sections = Section.query.all()
		return render_template("edit_book.html", book=book, sections=sections)

	else:
		flash("You need to login as librarian to edit books!", "warning")
		return redirect(url_for("librarian_login"))

@app.route("/delete-book/<int:book_id>", methods=["POST"])
def delete_book(book_id):
	if "lib_id" in session:
		BookRequest.query.filter_by(book_id=book_id).delete()
		IssuedBook.query.filter_by(book_id=book_id).delete()
		BookFeedback.query.filter_by(book_id=book_id).delete()
		db.session.delete(Book.query.get(book_id))
		db.session.commit()
		flash("Book deleted successfully", "success")
		return redirect(url_for("librarian"))
	else:
		flash("You need to login as librarian to delete books!", "warning")
		return redirect(url_for("librarian_login"))

@app.route("/process-request", methods=["POST"])
def process_request():
	if "lib_id" not in session:
		flash("You need to login as librarian to perform this action", "warning")
		return redirect(url_for("librarian_login"))

	request_id = request.form["request_id"]
	action = request.form["action"]
	if action == "Accepted":
		book_request = BookRequest.query.get(request_id)
		issued_book = IssuedBook(user_id=book_request.user_id, book_id=book_request.book_id)
		db.session.add(issued_book)
		db.session.delete(book_request)
		db.session.commit()
		flash("Request accepted successfully", "success")

	elif action == "Declined":
		book_request = BookRequest.query.get(request_id)
		db.session.delete(book_request)
		db.session.commit()
		flash("Request declined successfully", "success")
	
	else:
		flash("Invalid action", "danger")
	return redirect(url_for("librarian"))

@app.route("/book/<int:book_id>")
def book_details(book_id):
	if "lib_id" in session:
		b = Book.query.get(book_id)
		return render_template("book_details.html", book = b)
	else:
		flash("You need to login as librarian to view this page!", "warning")
		return render_template("librarian_login")

@app.route("/issue-books", methods=["POST"])
def issue_books():
	if "lib_id" in session:
		if request.method == "POST":
			user_id = request.form.get("user_id")
			book_ids = request.form.getlist("book_ids")

			for book_id in book_ids:
				existing_issued_book = IssuedBook.query.filter_by(user_id=user_id, book_id=book_id).first()
				if existing_issued_book:
					flash(f"Book '{existing_issued_book.book.title}' is already issued to this user", "warning")
				else:
					issued_book = IssuedBook(user_id=user_id, book_id=book_id)
					db.session.add(issued_book)

			db.session.commit()
			flash("Books issued successfully", "success")
			return redirect(url_for("librarian"))
	else:
		flash("You need to login as librarian to issue books!", "warning")
		return redirect(url_for("librarian_login"))

@app.route("/revoke-access/<int:user_id>", methods=["POST"])
def revoke_access(user_id):
	if request.method == "POST":
		book_id = request.form.get("book_id")
		user = User.query.get(user_id)
		if user:
			issued_book = IssuedBook.query.filter_by(user_id=user_id, book_id=book_id).first()
			if issued_book:
				db.session.delete(issued_book)
				db.session.commit()
				flash("Access revoked successfully", "success")
			else:
				flash("This book is not currently issued to the user", "warning")
		else:
			flash("User not found", "danger")
	return redirect(url_for("librarian"))

@app.route("/monitor-books")
def monitor_books():
	if "lib_id" in session:
		books = Book.query.all()
		return render_template("monitor_books.html", books=books)
	else:
		flash("You need to login as librarian to manage users", "warning")
		return redirect(url_for("librarian_login"))

@app.route("/librarian-logout")
def librarian_logout():
	if "lib_id" not in session:
		flash("You were not logged in!", "warning")
	else:
		flash("You have been logged out!", "success")
	session.pop("lib_id", None)
	return redirect(url_for("home"))


if __name__ == "__main__":
	with app.app_context():
		db.create_all()
	app.run(debug = True)