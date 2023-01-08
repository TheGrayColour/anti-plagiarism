import argparse
import ast
import re


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(dest="input_file", help="File containing pairs of file paths to check for plagiarism",
                        type=argparse.FileType("r", encoding='utf-8'))
    parser.add_argument(dest="output_file", help="Output file where score for each pair will be written")
    args = parser.parse_args()

    return args


def levenshtein_distance(s1, s2):  # расстояние Левенштейна

    m = len(s1)
    n = len(s2)

    dp = [[0 for _ in range(n + 1)] for _ in range(m + 1)]

    for i in range(1, m + 1):
        dp[i][0] = i

    for j in range(1, n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i - 1] != s2[j - 1]:
                insert = dp[i][j - 1] + 1  # вставляем в первую строку символ, который есть во второй,
                # и сокращаем (удаление из второй строки)
                delete = dp[i - 1][j] + 1  # удаление из первой строки
                replace = dp[i - 1][j - 1] + 1  # заменяем символ в первой строке, который есть во второй,
                # и потом сокращаем оба (удаление из 2 строк)

                dp[i][j] = min(insert, delete, replace)

            else:
                dp[i][j] = dp[i - 1][j - 1]

    return dp[m][n]


def sort_current_list(current_module_node_type, current_list):
    if current_module_node_type == ast.Import:
        return sorted(current_list, key=lambda x: re.sub('_', '', x.names[0].name.lower()))

    if current_module_node_type == ast.ImportFrom:
        return sorted(current_list, key=lambda x: re.sub('_', '', x.module.lower()) if x.module else "")
        # from . import case

    if current_module_node_type == ast.FunctionDef:
        return sorted(current_list, key=lambda x: re.sub('_', '', x.name.lower()))

    if current_module_node_type == ast.ClassDef:
        return sorted(current_list, key=lambda x: re.sub('_', '', x.name.lower()))

    if current_module_node_type == ast.AsyncFunctionDef:
        return sorted(current_list, key=lambda x: re.sub('_', '', x.name.lower()))

    return current_list


def remove_docstrings(body):
    edited_body = []

    for node in body:
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Str):
            edited_body.append(node)

    return edited_body


def lexicographically_sort_names(body):
    edited_list = []

    func_list = []
    class_list = []
    async_func_list = []
    import_list = []
    import_from_list = []
    other_list = []

    for module_node in body:

        if type(module_node) == ast.FunctionDef:
            func_list.append(module_node)
        elif type(module_node) == ast.ClassDef:
            class_list.append(module_node)
        elif type(module_node) == ast.AsyncFunctionDef:
            async_func_list.append(module_node)
        elif type(module_node) == ast.Import:
            import_list.append(module_node)
        elif type(module_node) == ast.ImportFrom:
            import_from_list.append(module_node)
        else:
            other_list.append(module_node)

    edited_list += sort_current_list(ast.Import, import_list)
    edited_list += sort_current_list(ast.ImportFrom, import_from_list)
    edited_list += sort_current_list(ast.ClassDef, class_list)
    edited_list += sort_current_list(ast.AsyncFunctionDef, async_func_list)
    edited_list += sort_current_list(ast.FunctionDef, func_list)
    edited_list += other_list

    return edited_list


def fix_some_syntax(script):
    # fix syntax for ast to work
    # plagiat1\mlp.py # """ case
    script = re.sub(r'(^ *#.*)"""', '"""', script, flags=re.MULTILINE)

    # remove comments which are the whole line
    script = re.sub(r'^ *#.*', '', script, flags=re.MULTILINE)

    # remove empty lines
    script = re.sub(r'^ *\n', "", script, flags=re.MULTILINE)

    # empty class case plagiat2\base.py
    script = re.sub(r'(^class .+:\n)([^ ])', r'\g<1>    """"""\n\g<2>', script, flags=re.MULTILINE)

    # in/for/is/del/def/return cases
    script = re.sub(r'\b(in|for|is|del|def|return)\b( *[.,=:])', r'\g<1>p\g<2>', script)
    script = re.sub(r'\b(in|for|is|del|def)\b([()[\]])', r'\g<1>p\g<2>', script)
    script = re.sub(r'\b(def)\b( +[()[\]])', r'\g<1>p\g<2>', script)
    script = re.sub(r'\b(return)\b( *[)\]])', r'\g<1>p\g<2>', script)
    script = re.sub(r'(= *)\b(in|is|for|del|def|return)\b', r'\g<1>\g<2>p', script)

    return script


def format_script(script):
    script = fix_some_syntax(script)

    ast_tree = ast.parse(script)

    for node in ast.walk(ast_tree):

        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            # remove docstrings """""" and ""
            node.body = remove_docstrings(node.body)
            # lexicographically sort everything and keep in the same order of node types it was before
            node.body = lexicographically_sort_names(node.body)

    script = ast.unparse(ast_tree)

    return script


def plagiarism_check(first_script_path, second_script_path):

    with open(first_script_path, "r", encoding="utf-8") as first_file:
        first_script = first_file.read()

    with open(second_script_path, "r", encoding="utf-8") as second_file:
        second_script = second_file.read()

    first_script = format_script(first_script)
    second_script = format_script(second_script)

    first_script = re.sub(r'[^a-zA-Z0-9]', '', first_script.lower())
    second_script = re.sub(r'[^a-zA-Z0-9]', '', second_script.lower())

    m = len(first_script)
    n = len(second_script)

    if m == 0 and n == 0:
        return 1.0

    return round((max(m, n) - levenshtein_distance(first_script, second_script)) / max(m, n), 3)


def main():

    # input
    args = parse_args()

    input_list = args.input_file.read().splitlines()
    args.input_file.close()

    with open(args.output_file, "w"):  # create file if it doesn't exist and clean it
        pass

    for i in input_list:

        paths = i.split(" ")
        score = plagiarism_check(paths[0], paths[1])

        with open(args.output_file, "a+") as output:
            output.write(str(score) + "\n")

    return


if __name__ == '__main__':
    main()
