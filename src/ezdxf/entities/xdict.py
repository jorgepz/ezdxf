# Copyright (c) 2019-2021 Manfred Moitzi
# License: MIT License
from typing import TYPE_CHECKING, Union, Optional
from ezdxf.lldxf.tags import Tags
from ezdxf.lldxf.const import DXFStructureError, DXFValueError
from ezdxf.lldxf.const import (
    ACAD_XDICTIONARY,
    XDICT_HANDLE_CODE,
    APP_DATA_MARKER,
)

if TYPE_CHECKING:
    from ezdxf.lldxf.tagwriter import TagWriter
    from ezdxf.eztypes import (
        Dictionary,
        Drawing,
        DXFEntity,
        DXFObject,
        Placeholder,
        DictionaryVar,
        XRecord,
    )

__all__ = ["ExtensionDict"]


# Example for table head and -entries with extension dicts:
# AutodeskSamples\lineweights.dxf


class ExtensionDict:
    """Stores extended data of entities in app data 'ACAD_XDICTIONARY', app
    data contains just one entry to a hard-owned DICTIONARY objects, which is
    not shared with other entities, each entity copy has its own extension
    dictionary and the extension dictionary is destroyed when the owner entity
    is deleted from database.

    """

    __slots__ = ("_xdict",)

    def __init__(self, xdict: Union[str, "Dictionary"]):
        # 1st loading stage: xdict as string -> handle to dict
        # 2nd loading stage: xdict as DXF Dictionary
        # This is not suitable for "mypy"
        self._xdict = xdict

    @property
    def dictionary(self) -> "Dictionary":
        """Returns the underlying :class:`~ezdxf.entities.Dictionary` object."""
        xdict = self._xdict
        assert xdict is not None, "destroyed extension dictionary"
        assert not isinstance(xdict, str), "dictionary handle not resolved"
        return xdict

    @property
    def handle(self) -> str:
        """Returns the handle of the underlying :class:`~ezdxf.entities.Dictionary`
        object.
        """
        return self.dictionary.dxf.handle

    def __getitem__(self, key: str):
        return self.dictionary[key]

    def __setitem__(self, key: str, value):
        self.dictionary[key] = value

    def __contains__(self, key: str):
        return key in self.dictionary

    def get(self, key: str, default=None) -> Optional["DXFEntity"]:
        return self.dictionary.get(key, default)

    @classmethod
    def new(cls, owner_handle: str, doc: "Drawing"):
        xdict = doc.objects.add_dictionary(
            owner=owner_handle,
            # All data in the extension dictionary belongs only to the owner
            hard_owned=True,
        )
        return cls(xdict)

    @property
    def is_alive(self):
        """Returns ``True`` if the underlying :class:`~ezdxf.entities.Dictionary`
        object is not deleted.
        """
        # Can not check if _xdict (as handle or Dictionary) really exist:
        return self._xdict is not None

    def update_owner(self, handle: str) -> None:
        """Update owner tag of underlying :class:`~ezdxf.entities.Dictionary`
        object.

        Internal API.
        """
        assert self.is_alive, "destroyed extension dictionary"
        self.dictionary.dxf.owner = handle

    @classmethod
    def from_tags(cls, tags: Tags):
        assert tags is not None
        # Expected DXF structure:
        # [(102, '{ACAD_XDICTIONARY', (360, handle), (102, '}')]
        if len(tags) != 3 or tags[1].code != XDICT_HANDLE_CODE:
            raise DXFStructureError("ACAD_XDICTIONARY error.")
        return cls(tags[1].value)

    def load_resources(self, doc: "Drawing") -> None:
        handle = self._xdict
        assert isinstance(handle, str)
        self._xdict = doc.entitydb.get(handle)

    def export_dxf(self, tagwriter: "TagWriter") -> None:
        assert self._xdict is not None
        xdict = self._xdict
        handle = xdict if isinstance(xdict, str) else xdict.dxf.handle
        tagwriter.write_tag2(APP_DATA_MARKER, ACAD_XDICTIONARY)
        tagwriter.write_tag2(XDICT_HANDLE_CODE, handle)
        tagwriter.write_tag2(APP_DATA_MARKER, "}")

    def destroy(self):
        """Destroy the underlying :class:`Dictionary` object."""
        xdict = self._xdict
        if xdict is not None and not isinstance(xdict, str) and xdict.is_alive:
            xdict.destroy()
        self._xdict = None

    def add_dictionary(
        self, name: str, hard_owned: bool = False
    ) -> "Dictionary":
        dictionary = self.dictionary
        doc = dictionary.doc
        assert doc is not None, "valid DXF document required"
        new_dict = doc.objects.add_dictionary(
            owner=dictionary.dxf.hande,
            hard_owned=hard_owned,
        )
        dictionary[name] = new_dict
        return new_dict

    def add_xrecord(self, name: str) -> "XRecord":
        dictionary = self.dictionary
        doc = dictionary.doc
        assert doc is not None, "valid DXF document required"
        xrecord = doc.objects.add_xrecord(dictionary.dxf.handle)
        dictionary[name] = xrecord
        return xrecord

    def add_dictionary_var(self, name: str, value: str) -> "DictionaryVar":
        dictionary = self.dictionary
        doc = dictionary.doc
        assert doc is not None, "valid DXF document required"
        dict_var = doc.objects.add_dictionary_var(
            dictionary.dxf.handle, value
        )
        dictionary[name] = dict_var
        return dict_var

    def add_placeholder(self, name: str) -> "Placeholder":
        dictionary = self.dictionary
        doc = dictionary.doc
        assert doc is not None, "valid DXF document required"
        placeholder = doc.objects.add_placeholder(
            dictionary.dxf.handle
        )
        dictionary[name] = placeholder
        return placeholder

    def link_dxf_object(self, name: str, obj: "DXFObject") -> None:
        """Link `obj` to the extension dictionary.

        Linked objects are owned by the extensions dictionary and therefore
        cannot be a graphical entity, which have to be owned by a
        :class:`~ezdxf.layouts.BaseLayout`.

        Raises:
            DXFTypeError: `obj` has invalid DXF type

        """
        self.dictionary.link_dxf_object(name, obj)
