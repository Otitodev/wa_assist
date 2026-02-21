class Cat:
    def __init__(self, name, age):
        self.name = name
        self.age = age

    def meow(self):
        print(f"{self.name} says meow!")

    def lives(self):
        print(f"{self.name} has 9 lives!")



Cat1 = Cat("Whiskers", 3)
Cat1.meow()
Cat1.lives()


class Cart:
    def __init__(self):
        self.items = []

    def add(self, item):
        self.items.append(item)
    
    def remove(self, item):
        if item in self.items:
            self.items.remove(item)
        else:
            print(f"{item} not in cart")

    def view(self):
        print(self.items)