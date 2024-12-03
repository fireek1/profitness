from fastapi import FastAPI, Form, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from database import SessionLocal, User, Product, Purchase

app = FastAPI()

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Зависимость для работы с БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Главная страница
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    user_id = request.cookies.get("user_id")  # Проверяем, есть ли идентификатор пользователя
    return templates.TemplateResponse("index.html", {"request": request, "user_id": user_id})


# Страница регистрации
@app.get("/register", response_class=HTMLResponse)
def register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
def register_user(
    username: str = Form(...), password: str = Form(...), name: str = Form(...), gender: str = Form(...), age: str = Form(...), db: Session = Depends(get_db)
):
    hashed_password = pwd_context.hash(password)
    new_user = User(username=username, password=hashed_password, name=name, gender=gender, age=age,  is_admin=False)
    db.add(new_user)
    db.commit()
    return RedirectResponse("/", status_code=302)


# Страница входа
@app.get("/login", response_class=HTMLResponse)
def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login_user(
    username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if user and pwd_context.verify(password, user.password):
        response = RedirectResponse("/menu", status_code=302)
        response.set_cookie("user_id", user.id)  # Сохраняем идентификатор пользователя в cookie
        return response
    return RedirectResponse("/login", status_code=302)


# Меню
@app.get("/menu", response_class=HTMLResponse)
def menu(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=302)  # Перенаправление на страницу входа

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return RedirectResponse("/login", status_code=302)  # Перенаправление на страницу входа

    products = db.query(Product).all()
    return templates.TemplateResponse(
        "menu.html",
        {
            "request": request,
            "products": products,
            "user": user,  # Передаем объект пользователя в шаблон
        },
    )


# Добавить данные для теста
@app.on_event("startup")
def populate_db():
    db = SessionLocal()
    if not db.query(Product).first():
        abonStandart = Product(
            name="Абонемент Стандарт",
            price=2999,
            description="Работает круглосутчно",
            stock=10,
        )
        abonSmol = Product(
            name="Абонемент Молодежный",
            price=1999,
            description="Работает до 18:00",
            stock=10,
        )
        db.add(abonStandart)
        db.add(abonSmol)
        db.commit()

@app.post("/menu/edit/{product_id}")
def edit_product(
    product_id: int,
    name: str = Form(...),
    price: float = Form(...),
    description: str = Form(...),
    stock: int = Form(...),
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product:
        product.name = name
        product.price = price
        product.description = description
        product.stock = stock
        db.commit()
    return RedirectResponse("/menu", status_code=302)


@app.post("/menu/buy/{product_id}")
def buy_product(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=302)  # Перенаправляем на страницу входа

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product or product.stock < 1:
        raise HTTPException(status_code=400, detail="Недостаточно товара в наличии")

    # Уменьшаем количество на складе
    product.stock -= 1

    # Добавляем запись о покупке
    new_purchase = Purchase(user_id=user_id, product_id=product_id)
    db.add(new_purchase)
    db.commit()

    return RedirectResponse("/menu", status_code=302)


@app.post("/menu/update_stock/{product_id}")
def update_stock(
    product_id: int,
    stock: int = Form(...),
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product:
        product.stock = stock
        db.commit()
    return RedirectResponse("/menu", status_code=302)


# Страница редактирования профиля клиента
@app.get("/client/edit", response_class=HTMLResponse)
def edit_client(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=302)  # Перенаправляем на страницу входа

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return templates.TemplateResponse("client_edit.html", {"request": request, "user": user})


@app.post("/client/edit")
def update_client(
    request: Request,
    name: str = Form(...),
    gender: str = Form(...),
    db: Session = Depends(get_db)
):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=302)  # Перенаправляем на страницу входа

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Обновляем данные пользователя
    user.name = name
    user.gender = gender
    db.commit()

    return RedirectResponse("/client/edit", status_code=302)  # Перенаправляем обратно на страницу редактирования


# Логика выхода пользователя
@app.get("/logout")
def logout(request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login")  # Перенаправляем, если пользователь не авторизован

    response = RedirectResponse(url="/")  # Перенаправляем на главную страницу
    response.delete_cookie("user_id")  # Удаляем cookie с идентификатором пользователя
    return response
