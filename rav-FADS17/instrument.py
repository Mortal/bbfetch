import os


def instrument_file(filename, fn):
    with open(filename) as fp:
        file_contents = fp.read()
    instrumented = fn(file_contents)
    if instrumented is None:
        return
    with open(filename + '.tmp', 'w') as fp:
        fp.write(instrumented)
    os.rename(filename + '.tmp', filename)


def find_class_base(file_contents, class_name):
    lines = file_contents.splitlines(keepends=True)
    line_offset = {1: 0}
    for i, line in enumerate(lines, 1):
        line_offset[i+1] = line_offset[i] + len(line)
    tree = javalang.parse.parse(file_contents)
    try:
        java_type = next(t for t in tree.types
                         if isinstance(t, javalang.tree.ClassDeclaration) and
                         t.name == class_name)
    except StopIteration:
        return None, None
    return java_type, line_offset


def find_class(file_contents, class_name):
    java_type, line_offset = find_class_base(file_contents, class_name)
    if java_type is None:
        return None, None
    line_no, col_offset = java_type.position
    position = line_offset[line_no] + col_offset - 1
    insert_position = file_contents.index('{', position) + 1
    return java_type, insert_position


def find_method_last_statement(file_contents, class_name, method_name):
    java_type, line_offset = find_class_base(file_contents, class_name)
    if java_type is None:
        return
    try:
        method = next(m for m in java_type.methods
                      if m.name == method_name)
    except StopIteration:
        print("%s has no method %s" % (class_name, method_name))
        return
    last_statement = method.body[-1]
    assert isinstance(last_statement, javalang.tree.ReturnStatement)
    line_no, col_offset = last_statement.position
    position = line_offset[line_no] + col_offset - 1
    return position


def field_names(java_type):
    return [d.name for f in java_type.fields for d in f.declarators]


def has_method(java_type, method_name):
    if any(m.name == method_name for m in java_type.methods):
        print('%s already has %s' % (java_type.name, method_name))
        return True


def instrument_augment_string(file_contents):
    java_type, insert_position = find_class(file_contents, 'Augment')
    if java_type is None:
        return
    method_name = 'toString'
    if has_method(java_type, method_name):
        return
    print('Add method %s() to %s' % (method_name, java_type.name))

    method_template = 'public String %s() { return %s; }'
    method_body = '"("+%s+")"' % (
        '+","+'.join('"%s="+%s' % (f, f) for f in field_names(java_type)))
    method = method_template % (method_name, method_body)
    return (file_contents[:insert_position] +
            method + file_contents[insert_position:])


def instrument_node_string(file_contents):
    java_type, insert_position = find_class(file_contents, 'Node')
    if java_type is None:
        return
    method_name = 'toString'
    if has_method(java_type, method_name):
        return
    fields = 'left key augment right'.split()
    if not set(fields).issubset(field_names(java_type)):
        return
    print('Add method %s() to %s' % (method_name, java_type.name))

    method = (
        'public String toString() { return ' +
        '"[" + left + ", " + key + "/" + augment + ", " + right + "]"; }')
    return (file_contents[:insert_position] +
            method + file_contents[insert_position:])


def instrument_combine_print(file_contents):
    position = find_method_last_statement(file_contents, 'Augment', 'combine')
    if position is None:
        return
    statement = ('System.out.println("combine(" + left + ' +
                 '", " + key + ", " + right + ") = " + res);')
    if statement not in file_contents:
        return (file_contents[:position] + statement + file_contents[position:])


try:
    import javalang
except ImportError:
    javalang = None
    print("Couldn't import javalang; instrumentation disabled.")
    print("Consider installing javalang with pip.")

    def instrument(filename):
        pass
else:
    def instrument(filename):
        if os.path.basename(filename) == 'Augment.java':
            instrument_file(filename, instrument_augment_string)
            instrument_file(filename, instrument_combine_print)
        if os.path.basename(filename) == 'Node.java':
            instrument_file(filename, instrument_node_string)
