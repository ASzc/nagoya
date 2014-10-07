#!/usr/bin/env python
# Should run in either Python 2 or Python 3

#
# Format Notes:
#
# https://httpd.apache.org/docs/current/configuring.html#syntax
#
# File as an ordered list of Nodes, which can be one or more lines in the file. Node Types:
#   Blank, one line
#   Comment, one line
#   Directives, one line, unless line ends with \ then value will continue on next line. Names can be non-unique, it's up to the application to interpret overrides, etc.
#   Sections, one or more lines, start and end with xml-like tags. May contain the above Nodes in a seperate namespace
# Ignoring Define variable expansion right now, as semantics are tricky when rewritten files need to still contain the variable signatures, rather than the interpreted values (variable context is unique per node in sequence, so can't be done from a global pool)
#

import re
import collections
import contextlib

#
# Attribute groups
#

def get_group_attr_name(group_name):
    return "_" + group_name

def equal_attr_group(group_name, o1, o2):
    group_attr_name = get_group_attr_name(group_name)
    ha = lambda o : hasattr(o, group_attr_name)
    gam = lambda o : set(map(lambda n : getattr(o, n), getattr(o, group_attr_name)))
    # Do both objects have the group, and are the members of that group equal?
    return ha(o1) and ha(o2) and gam(o1) == gam(o2)

@contextlib.contextmanager
def group_attrs(obj, group_name):
    # Detect attribute changes
    old_dir = set(dir(obj))
    yield
    new_dir = set(dir(obj))
    dir_diff = old_dir - new_dir

    group_attr_name = get_group_attr_name(group_name)
    if hasattr(obj, group_attr_name):
        # union
        group = getattr(obj, group_attr_name) | dir_diff
    else:
        group = dir_diff
    setattr(obj, group_attr_name, group)

#
# Line ending functions
#

def split_line_end(string):
    if string.endswith("\r\n"):
        body = string[:-2]
        end = string[-2:]
    elif string.endswith("\n"):
        body = string[:-1]
        end = string[-1:]
    return (body,end)

line_ends_pattern = re.compile(r'(\r?\n)')
def prefix_line_ends(string):
    return line_ends_pattern.sub(r'\\\1', string)

#
# Class/Mixin for obj["Name"] over non duplicate Nodes with names
#

class NodeContainer(object):
    def nodes_with_name(self, name):
       for node in self.nodes:
           if hasattr(node, "name") and node.name == name:
               yield node

    def __getitem__(self, key):
        n = self.nodes_with_name(key)
        if n is None:
            raise IndexError("No node with name {0}".format(key))
        else:
            return next(n)

    def default_directive_indent(self):
        if hasattr(self, "preceding_whitespace"):
            return self.preceding_whitespace + "    "
        else:
            return ""

    def __setitem__(self, key, value):
        if isinstance(value, str):
            directive = DirectiveNode()
            directive.name = key
            try:
                directive.arguments = list(find_args(value))
            except ArgParserException as e:
                raise TypeError("Unable to parse string to directive arguments: {0}".format(e.message))
        elif isinstance(value, list):
            directive = DirectiveNode()
            directive.name = key
            directive.arguments = []
            for v in value:
                argument = Argument()
                argument.text = v
                directive.arguments.append(argument)
        else:
            directive = None

        found = False
        for i,node in enumerate(self.nodes):
            if hasattr(node, "name") and node.name == key:
                if directive is not None:
                    directive.preceding_whitespace = node.preceding_whitespace
                    directive.line_ending = node.line_ending
                    for new,old in zip(directive.arguments, node.arguments):
                        new.preceding_whitespace = old.preceding_whitespace
                    self.nodes[i] = directive
                else:
                    self.nodes[i] = value
                found = True
                break
        if not found:
            if directive is not None:
                if self.nodes == []:
                    # First subnode, guess based on container indent
                    directive.preceding_whitespace = self.default_directive_indent()
                else:
                    # Guess at the whitespace based on surroundings
                    for prev_node in reversed(self.nodes):
                        if hasattr(prev_node, "preceding_whitespace"):
                            directive.preceding_whitespace = prev_node.preceding_whitespace
                            break
                self.nodes.append(directive)
            else:
                self.nodes.append(value)

    def __delitem__(self, key):
        found = False
        for i,node in enumerate(self.nodes):
            if hasattr(node, "name") and node.name == key:
                del self.nodes[i]
                found = True
                break
        if not found:
            raise IndexError("No node with name {0}".format(key))

#
# Node classes
#

class KeyNonKeyEqual(object):
    # Based on type and identity attributes
    def __eq__(self, other):
        return equal_attr_group("key", self, other)

    # Based on __eq__ and all attributes
    def strong_eq(self, other):
        return self.__eq__(other) and equal_attr_group("non_key", self, other)

arg_escape_pattern = re.compile(r'("|\\")')
def escape_arg(string):
    return arg_escape_pattern.sub(r'\\\1', string)

class Argument(KeyNonKeyEqual):
    def __init__(self):
        super(Argument, self).__init__()

        with group_attrs(self, "key"):
            self.text = ""

        with group_attrs(self, "non_key"):
            self.preceding_whitespace = " "
            self.is_quoted = False

    def __str__(self):
        parts = []
        parts.append(prefix_line_ends(self.preceding_whitespace))
        if self.is_quoted or any([c.isspace() for c in self.text]):
            output_text = '"' + escape_arg(self.text) + '"'
        else:
            output_text = self.text
        parts.append(output_text)
        return "".join(parts)

class Node(KeyNonKeyEqual):
    def __init__(self):
        super(Node, self).__init__()

        with group_attrs(self, "key"):
            pass

        with group_attrs(self, "non_key"):
            self.line_ending = "\n"

class BlankNode(Node):
    def __init__(self):
        super(BlankNode, self).__init__()

        with group_attrs(self, "key"):
            self.whitespace = ""

    def __str__(self):
        return self.whitespace + self.line_ending

# Comment is always whole line, and starts at the beginning of a line
class CommentNode(Node):
    def __init__(self):
        super(CommentNode, self).__init__()

        with group_attrs(self, "key"):
            self.text = ""

        with group_attrs(self, "non_key"):
            self.preceding_whitespace = ""

    def __str__(self):
        return self.preceding_whitespace + "#" + self.text + self.line_ending

class DirectiveNode(Node):
    def __init__(self):
        super(DirectiveNode, self).__init__()

        with group_attrs(self, "key"):
            self.name = ""
            self.arguments = []

        with group_attrs(self, "non_key"):
            self.preceding_whitespace = ""

    def __str__(self):
        parts = []
        parts.append(self.preceding_whitespace)
        parts.append(self.name)
        for arg in self.arguments:
            parts.append(str(arg))
        parts.append(self.line_ending)
        return "".join(parts)

class SectionNode(NodeContainer, Node):
    def __init__(self):
        super(SectionNode, self).__init__()

        with group_attrs(self, "key"):
            self.name = ""
            self.arguments = []

        with group_attrs(self, "non_key"):
            self.nodes = []
            self.preceding_whitespace = ""
            self.open_line_ending = "\n"

    def __str__(self):
        parts = []
        parts.append(self.preceding_whitespace)
        parts.append("<")
        parts.append(self.name)
        for arg in self.arguments:
            parts.append(str(arg))
        parts.append(">")
        parts.append(self.open_line_ending)
        for node in self.nodes:
            parts.append(str(node))
        parts.append("</" + self.name + ">")
        parts.append(self.line_ending)
        return "".join(parts)

#
# Error classes
#

class ArgParserException(Exception):
    pass

class ConfParserException(Exception):
    def __init__(self, errors):
        super(ConfParserException, self).__init__("\n    " + "\n    ".join(map(str, errors)))
        self.errors = errors

class ParsingError(object):
    def __init__(self, line):
        self.line = line
        parts = []
        parts.append("[")
        parts.append(type(self).__name__)
        parts.append(" ")
        parts.append(str(line.num))
        parts.append("]: ")
        parts.append(line.body)
        self.message = "".join(parts)

    def __str__(self):
        return self.message

class UnexpectedSectionEnd(ParsingError):
    pass

class InvalidLine(ParsingError):
    pass

class UnterminatedLine(ParsingError):
    pass

class UnterminatedSection(ParsingError):
    def __init__(self, line, sections):
        super(UnterminatedSection, self).__init__(line)
        self.sections = sections

class InvalidArgumentList(ParsingError):
    def __init__(self, line, detail):
        super(InvalidArgumentList, self).__init__(line)
        self.detail = detail

#
# Conf class
#

# ex: # this is a comment
comment_pattern = re.compile(r'(?P<whitespace>\s*)#(?P<text>.*)')
# ex: <Section arg "arg arg">
section_open_pattern = re.compile(r'(?P<whitespace>\s*)<(?P<name>[^ ]+)(?P<arguments_blob>.+)\s*>', re.DOTALL)
# ex: </Section>
section_close_pattern = re.compile(r'(?P<whitespace>\s*)</(?P<name>[^ ]+)\s*>')
# ex: Directive arg "arg arg"
directive_pattern = re.compile(r'(?P<whitespace>\s*)(?P<name>[^ ]+)(?P<arguments_blob>.+)', re.DOTALL)
# ex: arg1   arg2     "  arg3  arg3 arg3 "  "arg4 \"arg4 \" arg4  "
def find_args(line):
    ws_chars = []
    arg_chars = []
    char_iter = enumerate(line)

    def create_arg(ws, text, quoted):
        arg = Argument()
        arg.preceding_whitespace = ws if ws else " "
        arg.text = text
        arg.is_quoted = quoted
        return arg

    while True:
        try:
            i,c = next(char_iter)
        except StopIteration:
            break

        # Start of quoted argument
        if c == '"':
            start_index = i
            whitespace = "".join(ws_chars)
            ws_chars = []
            escaped = False
            while True:
                try:
                    i,c = next(char_iter)
                except StopIteration:
                    raise ArgParserException("Unterminated quoted argument, starting at column {0}".format(start_index))

                if escaped:
                    if not c == '"':
                        arg_chars.append("\\")
                    arg_chars.append(c)
                    escaped = False
                elif c == '"':
                    break
                elif c == "\\":
                    escaped = True
                else:
                    arg_chars.append(c)

            argument = "".join(arg_chars)
            arg_chars = []
            yield create_arg(whitespace, argument, True)

        # Whitespace before argument
        elif c.isspace():
            ws_chars.append(c)

        # Start of non-quoted argument
        else:
            arg_chars.append(c)
            whitespace = "".join(ws_chars)
            ws_chars = []
            while True:
                try:
                    i,c = next(char_iter)
                except StopIteration:
                    break

                if c.isspace():
                    ws_chars.append(c)
                    break
                else:
                    arg_chars.append(c)

            argument = "".join(arg_chars)
            arg_chars = []
            yield create_arg(whitespace, argument, False)

class ApacheHttpdConf(NodeContainer):
    def __init__(self):
        # Data
        self.nodes = []

    def __eq__(self, other):
        self.nodes == other.nodes

    def read_file(self, path):
        # Binary mode is required to preserve line endings
        with open(path, "rb") as f:
            self.read_open_file(f)

    def read_open_file(self, open_file):
        errors = []
        open_sections = []

        line_iterator = enumerate(map(lambda b : b.decode("UTF-8"), open_file.readlines()))
        Line = collections.namedtuple("Line", ["num", "full", "body", "ending"])

        def next_line():
            num,full = next(line_iterator)
            body,end = split_line_end(full)
            return Line(num, full, body, end)

        def merge_lines(from_line):
            fulls = []
            line = from_line
            while True:
                if line.body.endswith("\\"):
                    fulls.append(line.body[:-1] + line.ending)
                else:
                    fulls.append(line.full)
                    break

                try:
                    line = next_line()
                except StopIteration:
                    raise UnterminatedLine(line)

            num = line.num
            full = "".join(fulls)
            body,end = split_line_end(full)
            return Line(num, full, body, end)

        def add_to_parent(node):
            if open_sections == []:
                self.nodes.append(node)
            else:
                open_sections[-1].nodes.append(node)

        while True:
            try:
                line = next_line()
            except StopIteration:
                if len(open_sections) > 0:
                    raise UnterminatedSection(line, open_sections)
                break

            # Comment?
            if line.full.lstrip().startswith("#"):

                match = comment_pattern.match(line.body)
                if match:
                    comment = CommentNode()
                    comment.preceding_whitespace = match.group("whitespace")
                    comment.text = match.group("text")
                    comment.line_ending = line.ending
                    add_to_parent(comment)
                else:
                    errors.append(InvalidLine(line))

            # Blank?
            elif len(line.full.strip()) == 0:
                blank = BlankNode()
                blank.whitespace = line.body
                blank.line_ending = line.ending
                add_to_parent(blank)

            # Section end?
            elif line.full.lstrip().startswith("</"):
                if len(open_sections) < 1:
                    errors.append(UnexpectedSectionEnd(line))
                else:
                    # Pop from sections stack
                    closing_section = open_sections.pop()
                    closing_section.line_ending = line.ending

                    match = section_close_pattern.match(line.full)
                    if match:
                        name = match.group("name")
                        if not name == closing_section.name:
                            errors.append(UnexpectedSectionEnd(line))
                    else:
                        errors.append(InvalidLine(line))

                    # Do not add to parent, already done when section started

            # Section start?
            elif line.full.lstrip().startswith("<"):
                if line.body.endswith("\\"):
                    merged_line = merge_lines(line)
                else:
                    merged_line = line

                match = section_open_pattern.match(merged_line.body)
                if match:
                    section = SectionNode()
                    section.preceding_whitespace = match.group("whitespace")
                    section.name = match.group("name")
                    section.open_line_ending = merged_line.ending
                    args_blob = match.group("arguments_blob")

                    try:
                        section.arguments = list(find_args(args_blob))
                    except ArgParserException as e:
                        errors.append(InvalidArgumentList(line, e.message))

                    add_to_parent(section)

                    # Push onto sections stack
                    open_sections.append(section)
                else:
                    errors.append(InvalidLine(line))

            # Directive?
            else:
                if line.body.endswith("\\"):
                    merged_line = merge_lines(line)
                else:
                    merged_line = line

                match = directive_pattern.match(merged_line.body)
                if match:
                    directive = DirectiveNode()
                    directive.preceding_whitespace = match.group("whitespace")
                    directive.name = match.group("name")
                    directive.line_ending = merged_line.ending
                    args_blob = match.group("arguments_blob")

                    try:
                        directive.arguments = list(find_args(args_blob))
                    except ArgParserException as e:
                        errors.append(InvalidArgumentList(line, e.message))

                    add_to_parent(directive)
                else:
                    errors.append(InvalidLine(line))

        if len(errors) > 0:
            raise ConfParserException(errors)

    def write_file(self, path):
        # Binary mode is required to preserve line endings
        with open(path, "wb") as f:
            self.write_open_file(f)

    def write_open_file(self, open_file):
        for node in self.nodes:
            node_string = str(node)
            open_file.write(node_string.encode("UTF-8"))
