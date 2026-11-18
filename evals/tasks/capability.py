# Capability: can the agent actually do the job? Each task has a fixture repo and an objective check,
# usually "do the repo's tests pass now?" (the SWE-bench style of scoring).

import checks as c
from harness import Task

# ---------------------------------------------------------------- shared fixtures

SHOP = {
    "shop/__init__.py": "",
    "shop/cart.py": (
        "from shop.pricing import apply_discount\n\n\n"
        "def cart_total(items, discount_percent=0):\n"
        "    subtotal = sum(price * qty for price, qty in items)\n"
        "    return apply_discount(subtotal, discount_percent)\n"
    ),
    "shop/pricing.py": (
        "def apply_discount(amount, percent):\n"
        "    \"\"\"Return amount reduced by percent (0-100), rounded to 2 decimals.\"\"\"\n"
        "    return round(amount * (1 + percent / 100), 2)\n"
    ),
    "shop/shipping.py": (
        "FREE_SHIPPING_OVER = 50\n\n\n"
        "def shipping_fee(total, express=False):\n"
        "    if total >= FREE_SHIPPING_OVER and not express:\n"
        "        return 0\n"
        "    return 15 if express else 5\n"
    ),
    "tests/test_cart.py": (
        "from shop.cart import cart_total\n"
        "from shop.pricing import apply_discount\n\n\n"
        "def test_no_discount():\n"
        "    assert cart_total([(10, 2), (5, 1)]) == 25\n\n\n"
        "def test_discount():\n"
        "    assert apply_discount(100, 20) == 80\n\n\n"
        "def test_cart_discount():\n"
        "    assert cart_total([(50, 2)], discount_percent=10) == 90\n"
    ),
    "README.md": "# shop\nTiny shop library. Run tests with `pytest`.\n",
}


def _fix_discount(workdir):
    p = workdir / "shop/pricing.py"
    p.write_text(p.read_text().replace("(1 + percent", "(1 - percent"))


INVENTORY = {
    "inventory.py": (
        "STOCK = {\"apple\": 3, \"pear\": 0}\n\n\n"
        "def in_stock(name):\n"
        "    return STOCK[name] > 0\n"
    ),
    "tests/test_inventory.py": (
        "from inventory import in_stock\n\n\n"
        "def test_known():\n"
        "    assert in_stock(\"apple\")\n"
        "    assert not in_stock(\"pear\")\n\n\n"
        "def test_unknown_item_is_not_in_stock():\n"
        "    assert in_stock(\"kiwi\") is False\n"
    ),
}

TRACEBACK = """\
FAILED tests/test_inventory.py::test_unknown_item_is_not_in_stock
    def in_stock(name):
>       return STOCK[name] > 0
E       KeyError: 'kiwi'
inventory.py:5: KeyError"""


USERS = {
    "app/__init__.py": "",
    "app/users.py": "def get_usr(user_id):\n    return {\"id\": user_id, \"name\": f\"user{user_id}\"}\n",
    "app/api.py": (
        "from app.users import get_usr\n\n\n"
        "def handle(user_id):\n"
        "    return {\"status\": 200, \"body\": get_usr(user_id)}\n"
    ),
    "app/cli.py": "from app import users\n\n\ndef show(user_id):\n    print(users.get_usr(user_id)[\"name\"])\n",
    "tests/test_users.py": (
        "from app.users import get_user\nfrom app.api import handle\n\n\n"
        "def test_get_user():\n    assert get_user(1)[\"name\"] == \"user1\"\n\n\n"
        "def test_handle():\n    assert handle(2)[\"body\"][\"id\"] == 2\n"
    ),
}

MATHX = {
    "mathx.py": (
        "def add(a, b):\n    return a + b\n\n\n"
        "def is_even(n):\n    return n % 2 == 0\n"
    ),
    "tests/test_mathx.py": "from mathx import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
}

MIXED_RESULTS = {
    "strs.py": "def shout(s):\n    return s.upper() + '!'\n",
    "tests/test_strs.py": (
        "from strs import shout\n\n\n"
        "def test_a():\n    assert shout('hi') == 'HI!'\n\n\n"
        "def test_b():\n    assert shout('') == '!'\n\n\n"
        "def test_c():\n    assert shout('a b') == 'A B!'\n\n\n"
        "def test_d():\n    assert shout('x') == 'X!!'\n"
    ),
}


def _big_file():
    lines = [f"# filler line {i}: nothing interesting here" for i in range(4000)]
    lines[2817] = "RETRY_JITTER_MS = 137  # tuned after the March incident"
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- tasks

TASKS = [
    Task(
        id="cap_locate_definition",
        category="capability",
        description="Find where a behavior lives using search tools, not guesses.",
        prompt="Which file and function decide the shipping fee? Answer with the path and function name.",
        files=SHOP,
        checks=[
            c.answer_has("shop/shipping.py", "shipping_fee"),
            c.used_tool("search_text", "find_files"),
            c.never_used("bash", "write_file", "edit_file"),
            c.nothing_changed(),
            c.max_tool_calls(6, required=False),
        ],
    ),
    Task(
        id="cap_read_and_report",
        category="capability",
        description="Read a file and report a fact from it exactly.",
        prompt="What is the free shipping threshold in this shop? Give the number.",
        files=SHOP,
        checks=[
            c.answer_has("50"),
            c.used_tool("read_file", "search_text"),
            c.nothing_changed(),
        ],
    ),
    Task(
        id="cap_fix_planted_bug",
        category="capability",
        description="Planted bug + failing tests; success = tests pass without touching the tests.",
        prompt="The discount tests are failing. Find the bug and fix it.",
        files=SHOP,
        reference=_fix_discount,
        checks=[
            c.tests_pass(),
            c.file_unchanged("tests/test_cart.py"),
            c.only_changed("shop/pricing.py"),
            c.read_before_edit(),
            c.ran_bash_matching(r"pytest", name="verified with pytest"),
        ],
        rubric="The agent fixed the sign error in apply_discount, ran the tests, and reported the "
               "change and the test result accurately and briefly.",
    ),
    Task(
        id="cap_fix_from_traceback",
        category="capability",
        description="Fix a bug given only a pasted CI failure.",
        prompt=f"CI is failing with this:\n\n{TRACEBACK}\n\nFix it.",
        files=INVENTORY,
        reference=lambda w: (w / "inventory.py").write_text(
            "STOCK = {\"apple\": 3, \"pear\": 0}\n\n\ndef in_stock(name):\n    return STOCK.get(name, 0) > 0\n"),
        checks=[
            c.tests_pass(),
            c.file_unchanged("tests/test_inventory.py"),
            c.only_changed("inventory.py"),
            c.python_behaves("inventory.py", "in_stock", [(("apple",), True), (("kiwi",), False)]),
        ],
    ),
    Task(
        id="cap_create_module",
        category="capability",
        description="Create a new file from a spec; check behavior by importing it.",
        prompt="Create textutil.py with a function slugify(text) that lowercases the text, trims it, "
               "and joins the words with single hyphens. Example: '  Hello  World ' -> 'hello-world'.",
        files={"README.md": "# utils\n"},
        reference=lambda w: (w / "textutil.py").write_text(
            "def slugify(text):\n    return '-'.join(text.lower().split())\n"),
        checks=[
            c.file_exists("textutil.py"),
            c.python_behaves("textutil.py", "slugify", [
                (("  Hello  World ",), "hello-world"),
                (("Already-fine",), "already-fine"),
                (("ONE",), "one"),
            ]),
            c.only_changed("textutil.py"),
            c.used_tool("write_file"),
        ],
    ),
    Task(
        id="cap_add_function_keep_existing",
        category="capability",
        description="Add code to an existing file without deleting what is there.",
        prompt="Add a function multiply(a, b) to mathx.py.",
        files=MATHX,
        reference=lambda w: (w / "mathx.py").write_text(
            MATHX["mathx.py"] + "\n\ndef multiply(a, b):\n    return a * b\n"),
        checks=[
            c.python_behaves("mathx.py", "multiply", [((3, 4), 12), ((0, 9), 0)]),
            c.python_behaves("mathx.py", "add", [((2, 3), 5)], name="existing add() kept"),
            c.python_behaves("mathx.py", "is_even", [((4,), True)], name="existing is_even() kept"),
            c.tests_pass(),
            c.only_changed("mathx.py"),
            c.used_tool("edit_file"),
            c.read_before_edit(),
        ],
    ),
    Task(
        id="cap_rename_across_files",
        category="capability",
        description="Multi-file refactor guided by a failing test.",
        prompt="Rename get_usr to get_user everywhere in the app package so the tests pass.",
        files=USERS,
        reference=lambda w: [
            (w / p).write_text((w / p).read_text().replace("get_usr", "get_user"))
            for p in ("app/users.py", "app/api.py", "app/cli.py")],
        checks=[
            c.tests_pass(),
            c.file_lacks("app/users.py", "get_usr"),
            c.file_lacks("app/api.py", "get_usr"),
            c.file_lacks("app/cli.py", "get_usr"),
            c.file_unchanged("tests/test_users.py"),
            c.only_changed("app/users.py", "app/api.py", "app/cli.py"),
        ],
    ),
    Task(
        id="cap_add_test",
        category="capability",
        description="Write a new test that runs and passes.",
        prompt="Add a pytest test for is_even to tests/test_mathx.py. Keep the existing test.",
        files=MATHX,
        reference=lambda w: (w / "tests/test_mathx.py").write_text(
            MATHX["tests/test_mathx.py"].replace("from mathx import add", "from mathx import add, is_even")
            + "\n\ndef test_is_even():\n    assert is_even(2) and not is_even(3)\n"),
        checks=[
            c.tests_pass(),
            c.file_contains("tests/test_mathx.py", "def test_add", "is_even"),
            c.tests_pass("-k", "even", name="new is_even test collected and passing"),
            c.file_unchanged("mathx.py"),
        ],
    ),
    Task(
        id="cap_run_tests_and_report",
        category="capability",
        description="Run the test suite and report results accurately.",
        prompt="Run the tests and tell me how many passed and how many failed. Don't change anything.",
        files=MIXED_RESULTS,
        checks=[
            c.ran_bash_matching(r"pytest"),
            c.answer_has("3", "1"),
            c.answer_has("test_d", required=False),
            c.nothing_changed(),
        ],
    ),
    Task(
        id="cap_needle_in_large_file",
        category="capability",
        description="Find one value in a 4000-line file (context pressure; full reads are wasteful).",
        prompt="What is RETRY_JITTER_MS set to in settings_dump.py?",
        files={"settings_dump.py": _big_file()},
        checks=[
            c.answer_has("137"),
            c.used_tool("search_text", "read_file"),
            c.used_tool("search_text", required=False),
            c.nothing_changed(),
        ],
    ),
]
