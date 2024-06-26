"""
@author: Gabriel RQ
@description: Describes an interface.
"""

import pygame
import os
import typing

from typing import Tuple, List, Dict, Literal, Optional, Callable, Union, overload
from ._conversion import _ConversionMapping
from ..managers import (
    _OverlayManager,
    _BindingManager,
    _ConditionBinding,
    _ComponentBinding,
)
from ..groups import ComponentGroup, ClickableGroup, HoverableGroup, InputGroup
from ..components.handled import _Component, DefaultComponentTypes
from ..components.handled._components import _HandledComponent
from ..util import percent_to_float

if typing.TYPE_CHECKING:
    from uuid import UUID


class Interface:
    def __init__(
        self,
        name: str,
        background: str,
        size: Tuple[int, int],
        components: List[Dict],
        display: Literal["default", "grid", "overlay"],
        rows: Optional[int] = None,
        columns: Optional[int] = None,
        parent: Optional[str] = None,
        styles: Optional[Dict[str, Dict]] = None,
    ) -> None:
        self.name = name
        self.display = display  # display type
        self.rows = rows
        self.columns = columns
        self.parent = parent  # parent interface, if overlayed
        self.size = size

        self._overlay = _OverlayManager(self.size)
        self._underlayer = _OverlayManager(self.size)

        self._bindings = _BindingManager()

        self._bg_color = (0, 0, 0, 0)
        self._bg_image: Optional[pygame.Surface] = None

        self._group = pygame.sprite.Group()  # main component group
        self._subgroups: List[pygame.sprite.Group] = []  # external sprites group
        self._component_type_groups: Dict[str, ComponentGroup] = {}

        self._components: List[_Component] = []
        self._style_classes = styles

        self._parse_background(background)
        self._parse_components(components)

    # Properties

    @property
    def width(self) -> int:
        return self.size[0]

    @property
    def height(self) -> int:
        return self.size[1]

    @property
    def components(self) -> List[_Component]:
        return self._components

    @property
    def overlay(self) -> _OverlayManager:
        return self._overlay

    @property
    def underlayer(self) -> _OverlayManager:
        return self._underlayer

    @property
    def component_mapping(self) -> Dict[str, _Component]:
        """
        Dictionary of the components in the interface, where `key` is the component ID, and `value` is the component instance.
        Ignore components with id equals to '_'.

        :returns: Components dictionary.
        """

        return {c.id: c for c in self._components if c.id != "_"}

    @property
    def background(self) -> str | pygame.Surface:
        if self._bg_image is not None:
            return self._bg_image

        return self._bg_color

    @background.setter
    def background(self, bg: str) -> None:
        self._parse_background(bg)

    # Update and Render

    def update(self, dt: float) -> None:
        """
        Updates the interface through `pygame.sprite.Group.update()`.
        This method also updates the subgroups and bindings.
        """

        self._group.update(dt=dt)

        if len(self._subgroups) > 0:
            for g in self._subgroups:
                g.update(dt=dt)

        self._bindings.handle()
        self._overlay.update_interfaces(dt=dt)

    def draw(self, surface: pygame.Surface) -> None:
        """
        Draws this interface to `surface`.

        :param surface: Pygame Surface to render this interface to.
        """

        # Renders the background
        if self._bg_image is not None:
            surface.blit(self._bg_image, (0, 0))
        else:
            if self.display != "overlay":
                surface.fill(self._bg_color)

        # Renders the underlayer
        self._underlayer.render(surface)

        # Renders the components
        self._group.draw(surface)

        # Render the subgroups
        if len(self._subgroups) > 0:
            for g in self._subgroups:
                g.draw(surface)

        # Renders the overlay
        self._overlay.render(surface)

    def handle(self, surface: pygame.Surface, dt: float) -> None:
        """
        Renders and updates the interface. This also handles hover.

        :param surface: Pygame surface to render the interface to.
        """

        self.update(dt)
        self.handle_hover()
        self.draw(surface)

    # Component event handling

    def emit_click(self, mpos: Tuple[int, int]) -> None:
        """
        Calls `Clickable.handle_click` for all `Clickable` components in the interface, through `ClickableGroup.handle_click`.

        :param mpos: Mouse position.
        """

        for group in self._component_type_groups:
            if isinstance((g := self._component_type_groups[group]), ClickableGroup):
                g.handle_click(mpos, interfaces=(self.name,))

    def emit_input(self, event) -> None:
        """
        Calls `Input.handle_input` for all `Input` components in the interface, through `InputGroup.handle_input`.

        :param event: Pygame event.
        """

        for group in self._component_type_groups:
            if isinstance((g := self._component_type_groups[group]), InputGroup):
                g.handle_input(event, interfaces=(self.name,))

    def handle_hover(self) -> None:
        """
        Calls `HoverableGroup.handle_hover` for all `Hoverable` components in the interface, through `HoverableGroup.handle_hover`
        """

        for group in self._component_type_groups:
            if isinstance((g := self._component_type_groups[group]), HoverableGroup):
                g.handle_hover(interfaces=(self.name,))

    # Bindings

    @overload
    def create_binding(
        self,
        c1: _Component,
        a1: str,
        c2: _Component,
        a2: str,
    ) -> "UUID":
        """
        Creates a binding between two components. When the first component's attribute changes, the second component's attribute will be updated to match it.

        :param c1: Component to bind.
        :param a1: Attribute of component 1.
        :param c2: Component to bind to.
        :param a2: Attribute of component 2.
        :return: The binding id.
        """

        ...

    @overload
    def create_binding(
        self,
        c1: _Component,
        a1: str,
        callback: Callable,
    ) -> "UUID":
        """
        Creates a binding between a component and a callback. The component's attribute will be constantly updated to match the callback return value.

        :param c1: Component to bind.
        :param a1: Attribute of the component.
        :param callback: Callback function that return the attribute updated value.
        :return: The binding id.
        """

        ...

    def create_binding(
        self,
        c1: _Component,
        a1: str,
        c2: Union[_Component, Callable],
        a2: Optional[str] = None,
    ) -> "UUID":
        if isinstance(c2, _HandledComponent) and a2 is not None:
            b = _ComponentBinding("component")
            b.set_component_binding((c1, a1), (c2, a2))
        elif callable(c2):
            b = _ComponentBinding("callback")
            b.set_callback_binding((c1, a1), c2)

        return self._bindings.register(b)

    def when(
        self,
        condition: Callable[[None], bool],
        callback: Callable[[None], None],
        *,
        keep: bool = False,
    ) -> "UUID":
        """
        Binds a condition to a callback.

        :param condition: A function that returns a boolean indicating if the condition is met or not.
        :param callback: A function that is executed when the condition is met.
        :param keep: Wether to keep the binding after the condition is first met or not.
        :return: The binding id.
        """

        return self._bindings.register(_ConditionBinding(condition, callback, keep))

    def unbind(self, id_: "UUID") -> None:
        """
        Removes the binding with the provided `id`, if it exists.

        :param id_: Binding id.
        """

        self._bindings.unregister(id_)

    # Other

    def add_subgroup(self, group: pygame.sprite.Group) -> None:
        """
        Adds a subgroup to the interface. Subgroups are rendered and updated alognside the interface.

        :param group: A pygame Group.
        """

        if group not in self._subgroups:
            self._subgroups.append(group)

    def get_type_group(self, type_: str) -> Optional[ComponentGroup]:
        """
        Returns a specific component type group if it exists, otherwise None.

        :param type_: Component type.
        """

        return self._component_type_groups.get(type_)

    # Internal methods

    def _parse_background(self, bg) -> None:
        """
        Tries to load the 'background' interface attribute as an image, if it fails, considers it a color and uses it to fill the surface.
        """

        try:
            img = pygame.image.load(os.path.abspath(bg)).convert()

            if self.size != img.get_size():
                img = pygame.transform.scale(img, self.size)
            self._bg_image = img
        except:
            if bg is not None:
                self._bg_color = pygame.Color(bg)

    def _parse_components(self, components: List[Dict]) -> None:
        """
        Handles the parsing of the components loaded from the YAML interface file.

        :param interface_dict: Output of the YAML file load.
        """

        if self.display == "grid":
            # Calculate the size of a grid cell
            grid_width = self.size[0] // self.columns
            grid_height = self.size[1] // self.rows
        else:
            grid_width = grid_height = None

        for component in components:
            # Converts style class values
            self.__parse_style_classes(component)

            # Converts percentage values
            self.__parse_percentage_values(component, grid_width, grid_height)

            # Converts grid values
            self.__parse_grid_values(
                component,
                grid_width,
                grid_height,
                self.columns,
            )

            # Allows not setting any id for components that dont need it
            if "id" not in component:
                component["id"] = "_"

            component["pos"] = (component.get("x"), component.get("y"))
            component["size"] = (component.get("width"), component.get("height"))

            # instantiates a component according to it's type
            c = _ConversionMapping.convert_component(
                type_=component["type"].lower(),
                interface=self.name,
                **component,
            )

            self._components.append(c)

            # verifies if there's not a component group for it's type yet
            if c.type not in self._component_type_groups:
                self.__handle_new_type_group(c)

            # adds the component to it's groups
            self._component_type_groups[c.type].add(c)
            self._group.add(c)

    def __parse_percentage_values(
        self, component: Dict, gw: Optional[int] = None, gh: Optional[int] = None
    ) -> None:
        """
        Converts percentage values from a component's width, height, x and y atributes to integer values. PyInterfacer's WIDTH and HEIGHT atributes must be set for this to work.

        :param component: Dictionary representing the component.
        """

        # Use width and height values relative to the grid cell size, if component is positioned in a grid cell, otherwise relative to the window size
        width = gw if "grid_cell" in component else self.size[0]
        height = gh if "grid_cell" in component else self.size[1]

        if "width" in component and type(w := component["width"]) is str:
            if "%" in w:
                component["width"] = int(width * percent_to_float(w))
        if "height" in component and type(h := component["height"]) is str:
            if "%" in h:
                component["height"] = int(height * percent_to_float(h))

        # X and Y values are not taken into account for components with a grid cell specified, as they are always centered in their own cell
        if "x" in component and type(x := component["x"]) is str:
            if "%" in x:
                component["x"] = int(width * percent_to_float(x))
        if "y" in component and type(y := component["y"]) is str:
            if "%" in y:
                component["y"] = int(height * percent_to_float(y))

    def __parse_grid_values(
        self, component: Dict, gw: int, gh: int, columns: int
    ) -> None:
        """
        Converts the grid information into actual position and size information for each component.

        :param component: Dictionary representing the component.
        :param gw: Grid cell width.
        :param gh: Grid cell height.
        :param columns: Amount of columns in the grid.
        """

        if self.display != "grid":
            return

        if "grid_cell" in component:
            # calculate which row and column the component is at
            row = component["grid_cell"] // columns
            column = component["grid_cell"] % columns

            # centers the component position at it's grid position
            component["x"] = int((column * gw) + (gw / 2))
            component["y"] = int((row * gh) + (gh / 2))

            # if width and height are not provided, make the component use the grid's size instead; if they are provided as 'auto', use default component sizing behavior
            if "width" not in component:
                component["width"] = gw
            elif component["width"] == "auto":
                component["width"] = None
            if "height" not in component:
                component["height"] = gh
            elif component["height"] == "auto":
                component["height"] = None

    def __parse_style_classes(self, component: Dict) -> None:
        """
        Updates the component with it's style classes attributes.

        :param component: Dictionary representing the component.
        """

        # Verifies if the component sets style classes
        if "style" in component and self._style_classes is not None:
            # Handles a single style class
            if type(s := component["style"]) is str and s in self._style_classes:
                # Use only the styles defined in the style class that are not "overwritten" in the component declaration
                for attr, value in self._style_classes[s].items():
                    if attr not in component:
                        component[attr] = value
                return

            if len(component["style"]) == 0:
                return

            # Handles multiple style classes
            for style in component["style"]:
                if style in self._style_classes:
                    for attr, value in self._style_classes[style].items():
                        # By default, the component's style class attributes will be overwritten by the component's own attributes
                        # Because of the way this is handled, the order in which the style classes are declared matters. The first style class will have the highest priority, and will not be overwritten by the following ones
                        if attr not in component:
                            component[attr] = value

    def __handle_new_type_group(self, component: _Component) -> None:
        """
        Creates new component groups for component types that don't have a group yet.

        :param component: A component instance.
        """

        if isinstance(component.subtype, DefaultComponentTypes):
            subtype = component.subtype.value
        else:
            subtype = component.subtype

        # Verifies if the component's type or subtype have a special group that should be used
        if component.type in _ConversionMapping.GROUP_CONVERSION_TABLE:
            self._component_type_groups[component.type] = (
                _ConversionMapping.GROUP_CONVERSION_TABLE[component.type]()
            )
        elif subtype in _ConversionMapping.GROUP_CONVERSION_TABLE:
            self._component_type_groups[component.type] = (
                _ConversionMapping.GROUP_CONVERSION_TABLE[subtype]()
            )
        else:
            self._component_type_groups[component.type] = (
                ComponentGroup()
            )  # otherwise use the most generic ComponentGroup

    # Magic operators

    def __getitem__(self, component: str) -> Optional[_Component]:
        idx = self._components.index(component)

        if idx != -1:
            return self.components[idx]

        return None
