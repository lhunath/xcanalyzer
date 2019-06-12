from ..language.models import SwiftTypeType, ObjcTypeType, SwiftExtensionScope


class XcFile():

    def __init__(self, filepath):
        self.filepath = filepath
        self.swift_types = None
        self.objc_types = None

    def __eq__(self, other):
        return self.filepath == other.filepath

    def __hash__(self):
        return hash(self.filepath)

    def __repr__(self):
        return "<XcFile> {}".format(self.filepath)
    
    @property
    def filename(self):
        return self.filepath.split('/')[-1]

    def swift_types_filtered(self, type_not_in=set()):
        assert type_not_in.issubset(SwiftTypeType.ALL)

        return [t for t in self.swift_types if t.type_identifier not in type_not_in]
    
    @property
    def swift_extensions(self):
        return [t for t in self.swift_types if t.type_identifier == SwiftTypeType.EXTENSION]
    

class XcGroup():

    def __init__(self,
                 group_path,
                 filepath,
                 is_project_relative=False,
                 groups=None,
                 files=None,
                 is_variant=False):
        self.group_path = group_path
        self.filepath = filepath
        self.is_project_relative = is_project_relative
        self.groups = groups or list()
        self.files = files or set()
        self.is_variant = is_variant

    def __eq__(self, other):
        return self.group_path == other.group_path

    def __hash__(self):
        return hash(self.group_path)

    def __repr__(self):
        return "<XcGroup> {} [{}]".format(self.group_path, self.filepath)
    
    @property
    def has_folder(self):
        return self.group_path == self.filepath
    

class XcProject():

    def __init__(self, dirpath, name, targets, groups, files):
        assert type(groups) == list

        self.dirpath = dirpath
        self.name = name
        self.targets = targets
        self.groups = groups
        self.root_files = files
    
    def targets_of_type(self, target_type):
        results = {t for t in self.targets if t.type == target_type}
        return sorted(results, key=lambda t: t.name)
    
    def target_with_name(self, name):
        candidates = [t for t in self.targets if t.name == name]

        if not candidates:
            return None
        
        return candidates[0]
    
    @property
    def targets_sorted_by_name(self):
        results = list(self.targets)
        return sorted(results, key=lambda t: t.name)
    
    @property
    def target_files(self):
        results = set()

        for target in self.targets:
            results |= target.files
        
        return results
    
    @property
    def target_less_files(self):
        return self.files - self.target_files
    
    @property
    def target_less_h_files(self):
        return set([f for f in self.target_less_files if f.filepath.endswith('.h')])
    
    @property
    def group_files(self):
        results = set()

        groups = self.groups.copy()

        while groups:
            group = groups.pop()
            results |= group.files
            groups += group.groups
        
        return results
    
    @property
    def nonregular_files(self):
        results = list()

        groups = self.groups.copy()

        while groups:
            group = groups.pop()

            if group.is_variant:
                continue
            
            for group_file in group.files:
                if not group_file.filepath.startswith(group.group_path):
                    results.append((group_file, group))

            groups += group.groups
        
        return results

    @property
    def files(self):
        return self.root_files | self.group_files
    
    def relative_path_for_file(self, xc_file):
        return ''.join([self.dirpath, xc_file.filepath])
    
    def file_with_name(self, name):
        for xc_file in self.files:
            if xc_file.filename == name:
                return xc_file
        
        return None
    
    def groups_filtered(self, filter_mode=None):
        """ Returns the list of path sorted by name of all groups in the project. """

        results = []

        remaining_groups = list()

        for group in self.groups:
            remaining_groups.append(group)

        while remaining_groups:
            # Look for current group and its path
            current_group = remaining_groups.pop()

            # Empty groups
            if filter_mode == 'empty':
                if not current_group.groups and not current_group.files:
                    results.append(current_group)
            
            # Relative to project groups
            elif filter_mode == 'project_relative':
                if current_group.is_project_relative:
                    results.append(current_group)
            
            # Without folder groups
            elif filter_mode == 'without_folder':
                if not current_group.is_variant and not current_group.has_folder:
                    results.append(current_group)
                
            # Variant groups
            elif filter_mode == 'variant':
                if current_group.is_variant:
                    results.append(current_group)
            
            # All groups
            else:
                # Add current group path
                results.append(current_group)

            # Add its children to be treated
            for subgroup in current_group.groups:
                remaining_groups.append(subgroup)
        
        return results
    
    @property
    def objc_files(self):
        """ Union of targets' objc files and target .h files. """
        results = set()

        # .h and .m targets' files
        for target in self.targets_sorted_by_name:
            results |= target.objc_files
        
        # .h target less files
        results |= self.target_less_h_files
        
        return results
    
    @property
    def objc_types(self):
        results = []

        for objc_file in self.objc_files:
            results += objc_file.objc_types
        
        return results

    def objc_types_filtered(self, type_in=ObjcTypeType.ALL):
        assert type_in.issubset(ObjcTypeType.ALL)

        results = {objc_type_type: [] for objc_type_type in type_in}
        
        for objc_type in self.objc_types:
            if objc_type.type_identifier not in type_in:
                continue
            
            results[objc_type.type_identifier].append(objc_type)

        return results

    @property
    def swift_files(self):
        """ All targets' swift files. """
        results = set()

        for target in self.targets_sorted_by_name:
            results |= target.swift_files

        return results

    def swift_types_filtered(self, type_in=SwiftTypeType.ALL, type_not_in=set(), flat=False):
        assert type_in.issubset(SwiftTypeType.ALL)
        assert type_not_in.issubset(SwiftTypeType.ALL)

        # `type_not_in` has priority
        if type_not_in:
            types = SwiftTypeType.ALL - type_not_in
        else:
            types = type_in

        grouped_results = {swift_type_type: [] for swift_type_type in types}
        
        for swift_type in self.swift_types:
            if swift_type.type_identifier not in types:
                continue
            
            grouped_results[swift_type.type_identifier].append(swift_type)

        if flat:
            results = []

            for swift_types in grouped_results.values():
                results += list(swift_types)

            return results
        else:
            return grouped_results
        
    @property
    def swift_types(self):
        results = []
        
        for swift_file in self.swift_files:
            results += swift_file.swift_types
        
        return results
    
    @property
    def swift_extensions_grouped_by_scope(self):
        file_scoped_extensions = []
        remaining_extensions = []

        # File scoped extensions
        for swift_file in self.swift_files:
            for swift_extension in swift_file.swift_extensions:
                non_extension_swift_types = swift_file.swift_types_filtered(type_not_in={SwiftTypeType.EXTENSION})

                if swift_extension.name in [t.name for t in non_extension_swift_types]:
                    file_scoped_extensions.append(swift_extension)
                else:
                    remaining_extensions.append(swift_extension)
        
        # Project-scoped extensions: Objc and swift
        objc_type_names = [t.name for t in self.objc_types]
        swift_type_names = [t.name for t in self.swift_types_filtered(type_not_in={SwiftTypeType.EXTENSION}, flat=True)]

        objc_scoped_extensions = []
        swift_scoped_extensions = []
        outer_extensions = []
        
        remaining_extensions.reverse()
        while remaining_extensions:
            extension = remaining_extensions.pop()
            if extension.name in objc_type_names:
                objc_scoped_extensions.append(extension)
            elif extension.name in swift_type_names:
                swift_scoped_extensions.append(extension)
            else:
                # Outer scoped extensions
                outer_extensions.append(extension)
        
        return {
            SwiftExtensionScope.FILE: file_scoped_extensions,
            SwiftExtensionScope.PROJECT_OBJC: objc_scoped_extensions,
            SwiftExtensionScope.PROJECT_SWIFT: swift_scoped_extensions,
            SwiftExtensionScope.OUTER: outer_extensions,
        }


class XcTarget():

    class Type():
        TEST = 'test'
        UI_TEST = 'ui_test'
        FRAMEWORK = 'framework'
        APP_EXTENSION = 'app_extension'
        WATCH_EXTENSION = 'watch_extension'
        APPLICATION = 'application'
        WATCH_APPLICATION = 'watch_application'
        OTHER = 'other'

        AVAILABLES = [  # Default order of display
            FRAMEWORK,
            APP_EXTENSION,
            WATCH_EXTENSION,
            WATCH_APPLICATION,
            APPLICATION,
            TEST,
            UI_TEST,
            OTHER,
        ]

    def __init__(self,
                 name,
                 target_type,
                 product_name,
                 dependencies=None,
                 linked_frameworks=None,
                 embed_frameworks=None,
                 source_files=None,
                 resource_files=None,
                 header_files=None,
                 linked_files=None):
        self.name = name
        self.type = target_type
        self.product_name = product_name
        self.dependencies = dependencies or set()  # Set of targets
        self.linked_frameworks = linked_frameworks or set()  # Set of targets
        self.embed_frameworks = embed_frameworks or set()  # Set of targets
        self.source_files = source_files or set()
        self.resource_files = resource_files or set()
        self.header_files = header_files or set()
        self.linked_files = linked_files or set()

    def __eq__(self, other):
        if self.type != other.type:
            return False
        elif self.name != other.name:
            return False
        return True
    
    def __hash__(self):
        return hash((self.type, self.name))

    def __repr__(self):
        return "<XcTarget> {}".format(self.name)
    
    @property
    def files(self):
        return self.source_files | self.resource_files | self.header_files | self.linked_files
    
    @property
    def swift_files(self):
        return set([f for f in self.source_files if f.filepath.endswith('.swift')])

    @property
    def h_files(self):
        return set([f for f in self.header_files if f.filepath.endswith('.h')])

    @property
    def m_files(self):
        return set([f for f in self.source_files if f.filepath.endswith('.m')])

    @property
    def objc_files(self):
        return self.h_files | self.m_files
