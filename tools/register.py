# GPL License

import bpy
import typing

__bl_classes = []
__bl_ordered_classes = []


def register_wrap(cls):
    if hasattr(cls, 'bl_rna'):
        __bl_classes.append(cls)
    cls = make_annotations(cls)
    return cls


def make_annotations(cls):
    bl_props = {k: v for k, v in cls.__dict__.items() if isinstance(v, bpy.props._PropertyDeferred)}
    if bl_props:
        if '__annotations__' not in cls.__dict__:
            cls.__annotations__ = {}
        annotations = cls.__dict__['__annotations__']
        for k, v in bl_props.items():
            annotations[k] = v
            delattr(cls, k)
    return cls


def get_ordered_classes():
    return __bl_ordered_classes


def order_classes():
    global __bl_ordered_classes
    classes_to_register = set(__bl_classes)
    deps_dict = {cls: set(iter_own_register_deps(cls, classes_to_register)) for cls in __bl_classes}

    __bl_ordered_classes = [cls for cls in __bl_classes if is_ui_class(cls)]

    for cls in toposort(deps_dict):
        if not is_ui_class(cls):
            __bl_ordered_classes.append(cls)


def is_ui_class(cls):
    module = cls.__module__
    return '.ui.' in module or module.endswith('.ui')


def iter_own_register_deps(cls, own_classes):
    yield from (dep for dep in iter_register_deps(cls) if dep in own_classes)


def iter_register_deps(cls):
    for value in typing.get_type_hints(cls, {}, {}).values():
        dependency = get_dependency_from_annotation(value)
        if dependency is not None:
            yield dependency


def get_dependency_from_annotation(value):
    if isinstance(value, bpy.props._PropertyDeferred):
        if value.function in (bpy.props.PointerProperty, bpy.props.CollectionProperty):
            return value.keywords.get("type")
    return None


def toposort(deps_dict):
    sorted_list = []
    sorted_values = set()
    while len(deps_dict) > 0:
        unsorted = []
        for value, deps in deps_dict.items():
            if len(deps) == 0:
                sorted_list.append(value)
                sorted_values.add(value)
            else:
                unsorted.append(value)
        if len(unsorted) == len(deps_dict):
            print('CATS: dependency cycle between', [cls.__name__ for cls in unsorted])
            sorted_list.extend(unsorted)
            break
        deps_dict = {value: deps_dict[value] - sorted_values for value in unsorted}
    return sorted_list
