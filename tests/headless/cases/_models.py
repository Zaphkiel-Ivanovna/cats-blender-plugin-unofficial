# GPL License
"""Synthetic armatures shaped to drive different branches of Fix Model."""

import random

import bpy
from mathutils import Vector

SPINE_CHAIN = [
    ("LowerBody", None, (0, 0, 0.9), (0, 0, 1.1)),
    ("UpperBody", "LowerBody", (0, 0, 1.1), (0, 0, 1.35)),
    ("Bip_Neck", "UpperBody", (0, 0, 1.5), (0, 0, 1.6)),
    ("Bip_Head", "Bip_Neck", (0, 0, 1.6), (0, 0, 1.75)),
]


def _limbs(extra_per_side=()):
    out = []
    for side, x in (("Left", 1), ("Right", -1)):
        out += [
            (f"{side}_Shoulder", "UpperBody", (0, 0, 1.45), (0.1 * x, 0, 1.45)),
            (f"{side}_Arm", f"{side}_Shoulder", (0.1 * x, 0, 1.45), (0.35 * x, 0, 1.4)),
            (f"{side}_Elbow", f"{side}_Arm", (0.35 * x, 0, 1.4), (0.6 * x, 0, 1.35)),
            (f"{side}_Wrist", f"{side}_Elbow", (0.6 * x, 0, 1.35), (0.7 * x, 0, 1.33)),
            (f"{side}_Leg", "LowerBody", (0.1 * x, 0, 0.9), (0.1 * x, 0, 0.5)),
            (f"{side}_Knee", f"{side}_Leg", (0.1 * x, 0, 0.5), (0.1 * x, 0, 0.1)),
            (f"{side}_Ankle", f"{side}_Knee", (0.1 * x, 0, 0.1), (0.1 * x, -0.1, 0.02)),
        ]
        for name, parent in extra_per_side:
            out.append((f"{name}_{side[0]}", parent.format(side=side),
                        (0.5 * x, 0, 1.37), (0.55 * x, 0, 1.37)))
    return out


JUNK = [
    ("LegIK_L", None, (0.1, 0, 0.1), (0.1, 0, 0.0)),
    ("LegIK_R", None, (-0.1, 0, 0.1), (-0.1, 0, 0.0)),
    ("_Dummy_L", "Left_Wrist", (0.7, 0, 1.33), (0.75, 0, 1.33)),
    ("ControlNode", None, (0, 0, 0), (0, 0, 0.1)),
    ("Center", None, (0, 0, 0.9), (0, 0, 1.0)),
]

TWIST = [("HandTwist", "{side}_Wrist"), ("ArmTwist", "{side}_Arm")]


def clear():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    scene = bpy.context.scene
    for name, value in (("keep_twist_bones", False), ("fix_twist_bones", True)):
        if hasattr(scene, name):
            setattr(scene, name, value)


def build_armature(bones, name="Armature"):
    data = bpy.data.armatures.new(name)
    armature = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(armature)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='EDIT')
    for bone_name, parent, head, tail in bones:
        bone = data.edit_bones.new(bone_name)
        bone.head, bone.tail = Vector(head), Vector(tail)
        if parent and parent in data.edit_bones:
            bone.parent = data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    return armature


def add_mesh(armature, name, subdivisions=3, shape_keys=0, materials=1, seed=0):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions, radius=0.9,
                                          location=(0, 0, 1.0))
    mesh = bpy.context.object
    mesh.name = name

    for i in range(materials):
        mesh.data.materials.append(bpy.data.materials.new(f"{name}_mat_{i}"))
    if materials > 1:
        for i, poly in enumerate(mesh.data.polygons):
            poly.material_index = i % materials

    rng = random.Random(seed)
    bone_names = [b.name for b in armature.data.bones]
    for bone_name in bone_names:
        mesh.vertex_groups.new(name=bone_name)
    for vertex in mesh.data.vertices:
        for bone_name in rng.sample(bone_names, min(3, len(bone_names))):
            mesh.vertex_groups[bone_name].add([vertex.index], rng.random(), 'REPLACE')

    if shape_keys:
        mesh.shape_key_add(name="Basis", from_mix=False)
        vrc = ['vrc.blink_left', 'vrc.blink_right', 'vrc.v_aa', 'vrc.v_ch',
               'vrc.v_dd', 'vrc.v_e', 'vrc.v_ff', 'vrc.v_ih']
        names = (vrc + [f"custom_{i}" for i in range(shape_keys)])[:shape_keys]
        rng.shuffle(names)
        for key_name in names:
            key = mesh.shape_key_add(name=key_name, from_mix=False)
            for i in range(0, len(key.data), 7):
                key.data[i].co.z += 0.001

    mesh.parent = armature
    mesh.modifiers.new("Armature", 'ARMATURE').object = armature
    return mesh


def mmd_raw():
    """An unprocessed MMD import: junk bones, several meshes, shape keys."""
    clear()
    armature = build_armature(SPINE_CHAIN + _limbs() + JUNK)
    add_mesh(armature, "Body", subdivisions=4, shape_keys=12, materials=3, seed=1)
    add_mesh(armature, "Hair", subdivisions=2, materials=2, seed=2)
    add_mesh(armature, "Cloth", subdivisions=2, seed=3)
    return armature


def with_twist_bones():
    """Twist bones, which Fix Model either keeps or merges."""
    clear()
    armature = build_armature(SPINE_CHAIN + _limbs(TWIST) + JUNK)
    add_mesh(armature, "Body", subdivisions=3, shape_keys=4, seed=4)
    return armature


def two_spines():
    """UpperBody and UpperBody2, which becomes Spine and Chest."""
    clear()
    chain = [
        ("LowerBody", None, (0, 0, 0.9), (0, 0, 1.1)),
        ("UpperBody", "LowerBody", (0, 0, 1.1), (0, 0, 1.2)),
        ("UpperBody2", "UpperBody", (0, 0, 1.2), (0, 0, 1.35)),
        ("Bip_Neck", "UpperBody2", (0, 0, 1.5), (0, 0, 1.6)),
        ("Bip_Head", "Bip_Neck", (0, 0, 1.6), (0, 0, 1.75)),
    ]
    armature = build_armature(chain + _limbs())
    add_mesh(armature, "Body", subdivisions=3, seed=5)
    return armature


def three_spines():
    """A three bone spine chain, which becomes Spine, Chest and Upper Chest."""
    clear()
    chain = [
        ("LowerBody", None, (0, 0, 0.9), (0, 0, 1.1)),
        ("UpperBody", "LowerBody", (0, 0, 1.1), (0, 0, 1.18)),
        ("UpperBody2", "UpperBody", (0, 0, 1.18), (0, 0, 1.26)),
        ("UpperBody3", "UpperBody2", (0, 0, 1.26), (0, 0, 1.35)),
        ("Bip_Neck", "UpperBody3", (0, 0, 1.5), (0, 0, 1.6)),
        ("Bip_Head", "Bip_Neck", (0, 0, 1.6), (0, 0, 1.75)),
    ]
    armature = build_armature(chain + _limbs())
    add_mesh(armature, "Body", subdivisions=3, seed=8)
    return armature


def twist_bones_kept():
    """Twist bones with keep_twist_bones on, which is off by default."""
    clear()
    armature = build_armature(SPINE_CHAIN + _limbs(TWIST) + JUNK)
    add_mesh(armature, "Body", subdivisions=3, seed=9)
    bpy.context.scene.keep_twist_bones = True
    bpy.context.scene.fix_twist_bones = False
    return armature


def no_spine():
    """Hips and limbs but nothing that maps to a spine."""
    clear()
    bones = [("LowerBody", None, (0, 0, 0.9), (0, 0, 1.1))]
    bones += [b for b in _limbs() if not b[1] or b[1] != "UpperBody"]
    armature = build_armature(bones)
    add_mesh(armature, "Body", subdivisions=2, seed=6)
    return armature


def already_clean():
    """Bones already carrying the names Fix Model would give them."""
    clear()
    bones = [
        ("Hips", None, (0, 0, 0.9), (0, 0, 1.1)),
        ("Spine", "Hips", (0, 0, 1.1), (0, 0, 1.35)),
        ("Chest", "Spine", (0, 0, 1.35), (0, 0, 1.5)),
        ("Neck", "Chest", (0, 0, 1.5), (0, 0, 1.6)),
        ("Head", "Neck", (0, 0, 1.6), (0, 0, 1.75)),
    ]
    for side, x in (("Left", 1), ("Right", -1)):
        bones += [
            (f"Shoulder.{side[0]}", "Chest", (0, 0, 1.45), (0.1 * x, 0, 1.45)),
            (f"Upper Arm.{side[0]}", f"Shoulder.{side[0]}", (0.1 * x, 0, 1.45), (0.35 * x, 0, 1.4)),
            (f"Lower Arm.{side[0]}", f"Upper Arm.{side[0]}", (0.35 * x, 0, 1.4), (0.6 * x, 0, 1.35)),
            (f"Hand.{side[0]}", f"Lower Arm.{side[0]}", (0.6 * x, 0, 1.35), (0.7 * x, 0, 1.33)),
            (f"Upper Leg.{side[0]}", "Hips", (0.1 * x, 0, 0.9), (0.1 * x, 0, 0.5)),
            (f"Lower Leg.{side[0]}", f"Upper Leg.{side[0]}", (0.1 * x, 0, 0.5), (0.1 * x, 0, 0.1)),
            (f"Foot.{side[0]}", f"Lower Leg.{side[0]}", (0.1 * x, 0, 0.1), (0.1 * x, -0.1, 0.02)),
        ]
    armature = build_armature(bones)
    add_mesh(armature, "Body", subdivisions=3, shape_keys=6, seed=7)
    return armature


def armature_only():
    """No mesh at all, which validation is meant to refuse."""
    clear()
    return build_armature(SPINE_CHAIN + _limbs())


ALL = {
    "mmd_raw": mmd_raw,
    "with_twist_bones": with_twist_bones,
    "twist_bones_kept": twist_bones_kept,
    "two_spines": two_spines,
    "three_spines": three_spines,
    "no_spine": no_spine,
    "already_clean": already_clean,
    "armature_only": armature_only,
}
