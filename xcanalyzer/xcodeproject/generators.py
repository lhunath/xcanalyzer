import os

from graphviz import Digraph
from termcolor import cprint

from ..language.models import SwiftTypeType, ObjcTypeType, SwiftExtensionScope

from .parsers import SwiftFileParser
from .models import XcTarget


class XcProjectGraphGenerator():

    def __init__(self, xcode_project):
        self.xcode_project = xcode_project
    
    def generate_targets_dependencies_graph(self,
                                            output_format='pdf',  # 'pdf' or 'png'
                                            dependency_type=None,  # 'build' or 'framework'
                                            preview=False,
                                            display_graph_source=False,
                                            filepath=None,
                                            title=None,
                                            including_types=set()):
        if not filepath:
            raise Exception("Missing filepath.")

        if not title:
            raise Exception("Missing title.")
        
        if output_format not in {'pdf', 'png'}:
            raise Exception("Bad output_format '{}'. Only 'pdf' and 'png' are supported.".format(output_format))
        
        if dependency_type not in {'build', 'linked', 'embed'}:
            raise Exception("Bad dependency_type '{}'. Only 'build', 'linked' and 'embed' are supported.".format(dependency_type))

        graph = Digraph(filename=filepath,
                        format=output_format,
                        engine='dot',
                        graph_attr={
                            'fontname': 'Courier',
                            'pack': 'true',
                        },
                        node_attr={
                            'shape': 'box',
                            'fontname': 'Courier',
                        },
                        edge_attr={
                            'fontname': 'Courier',
                        })

        title = "{} - {}\n\n".format(self.xcode_project.name, title)
        graph.attr(label=title)

        graph.attr(labelloc='t')
        graph.attr(fontsize='26')
        graph.attr(rankdir='BT')

        if including_types:
            targets = {t for t in self.xcode_project.targets if t.type in including_types}
        else:
            targets = self.xcode_project.targets

        # Sort nodes by name
        targets = sorted(targets, key=lambda t: t.name)

        # Target nodes
        for xcode_target in targets:
            if xcode_target.type in {XcTarget.Type.TEST, XcTarget.Type.UI_TEST}:
                style = 'dotted'
            elif xcode_target.type in {XcTarget.Type.APP_EXTENSION, XcTarget.Type.WATCH_EXTENSION}:
                style = 'dashed'
            elif xcode_target.type in {XcTarget.Type.APPLICATION, XcTarget.Type.WATCH_APPLICATION}:
                style = 'diagonals'
            else:
                style = 'solid'
            graph.node(xcode_target.name, style=style)

        # Dependencies edges
        for xcode_target in targets:
            if dependency_type == 'build':
                dependencies = xcode_target.dependencies
            elif dependency_type == 'linked':
                dependencies = xcode_target.linked_frameworks
            elif dependency_type == 'embed':
                dependencies = xcode_target.embed_frameworks
            else:
                raise Exception("Dependency type '{}' not supported.".format(dependency_type))

            dependencies_target = sorted(dependencies, key=lambda t: t.name)  # Sort dependencies by name
            for dependency_target in dependencies_target:
                if including_types and dependency_target.type not in including_types:
                    continue

                graph.edge(xcode_target.name, dependency_target.name)

        # Render the graph
        graph.render(cleanup=True, view=preview)

        # Display graph source if asked
        if display_graph_source:
            print(graph.source)

        return True


class FolderReporter():

    def __init__(self, folder_path, ignored_dirpaths, ignored_dirs):
        self.folder_path = folder_path
        self.ignored_dirpaths = ignored_dirpaths
        self.ignored_dirs = ignored_dirs
    
    def print_empty_dirs(self):
        # Walk to find empty folders
        for (dirpath, dirnames, filenames) in os.walk(self.folder_path):
            relative_dirpath = dirpath[len(self.folder_path):]

            # Filter root folder
            if not relative_dirpath:
                continue

            # Filter folder to ignore by path
            continue_to_next_dirpath = False
            for ignored_dirpath in self.ignored_dirpaths:
                if relative_dirpath.startswith(ignored_dirpath):
                    continue_to_next_dirpath = True
                    break
            if continue_to_next_dirpath:
                continue
                
            # Filter folder to ignore by name
            folder_parts = set(relative_dirpath.split(os.path.sep))
            if self.ignored_dirs & folder_parts:
                continue
            
            # Filter folder containing at least one dir
            if dirnames:
                continue
            
            # Filter folder containing at least an unhidden filename
            unhidden_filenames = set([f for f in filenames if not f.startswith('.')])
            if unhidden_filenames:
                continue
            
            # Hidden files
            hidden_filenames = list(set(filenames) - unhidden_filenames)
            hidden_filenames.sort()

            display = relative_dirpath

            # Display hidden files for folder with only hidden files
            if hidden_filenames:
                hidden_filenames_display = ', '.join([f for f in hidden_filenames])
                display += ' [{}]'.format(hidden_filenames_display)
            
            print(display)


class XcProjReporter():

    def __init__(self, xcode_project):
        self.xcode_project = xcode_project

    def _print_horizontal_line(self):
        print('--------------------')

    def print_targets(self, by_type=True, verbose=False):
        if not by_type:
            target_names = [t.name for t in self.xcode_project.targets]
            target_names.sort()
            for target_name in target_names:
                print(target_name)
        else:
            self.target_type_counts = dict()

            for target_type in XcTarget.Type.AVAILABLES:
                targets = self.xcode_project.targets_of_type(target_type)

                if not targets:
                    self.target_type_counts[target_type] = (None, len(targets))
                    continue

                # Target type
                target_type_display = '{}s'.format(target_type.replace('_', ' ').capitalize())
                cprint('{} ({}):'.format(target_type_display, len(targets)), attrs=['bold'])

                # Targets
                for target in targets:
                    if verbose:
                        text = '- {} => {}'.format(target.name, target.product_name)
                    else:
                        text = '- {}'.format(target.name)
                    print(text)
                
                self.target_type_counts[target_type] = (target_type_display, len(targets))
    
    def print_targets_summary(self):
        # Targets summary
        self._print_horizontal_line()

        for target_type in XcTarget.Type.AVAILABLES:
            if self.target_type_counts[target_type][1]:
                print('{:>2} {}'.format(self.target_type_counts[target_type][1],
                                        self.target_type_counts[target_type][0]))
        cprint('{:>2} Targets in total'.format(len(self.xcode_project.targets)), attrs=['bold'])

    def print_files_by_targets(self):
        for target in self.xcode_project.targets_sorted_by_name:
            counters = [
                '{} source files'.format(len(target.source_files)),
                '{} resource files'.format(len(target.resource_files)),
                '{} header files'.format(len(target.header_files)),
                '{} linked files'.format(len(target.linked_files)),
            ]
            target_display = '{} [{}]:'.format(target.name, ', '.join(counters))
            cprint(target_display, attrs=['bold'])

            # Files of the target
            filepaths = [f.filepath for f in list(target.files)]
            filepaths.sort()
            for filepath in filepaths:
                print(filepath)

    def _print_swift_types(self, swift_files):
        for swift_file in swift_files:
            cprint(swift_file.filepath, attrs=['bold'])
            for swift_type in swift_file.swift_types:
                print(swift_type)
    
    def _print_objc_types(self, objc_files):
        for objc_file in objc_files:
            cprint(objc_file.filepath, attrs=['bold'])
            for objc_type in objc_file.objc_types:
                print(objc_type)

    def print_types_by_file(self, languages):
        # Swift types
        for target in self.xcode_project.targets_sorted_by_name:
            # Target
            cprint('=> {}'.format(target.name), attrs=['bold'])

            # Swift files
            if 'swift' in languages:
                self._print_swift_types(target.swift_files)
            
            # Objective-C .m files
            if 'objc' in languages:
                self._print_objc_types(target.objc_files)
            
            print()  # Empty line
        
        # Objective-C types from project .h files
        if 'objc' in languages:
            cprint('=> Project "target less" .h files', attrs=['bold'])
            self._print_objc_types(self.xcode_project.target_less_h_files)
    
    def print_types_summary(self, languages):
        assert languages

        self._print_horizontal_line()

        if 'swift' in languages:
            self._print_swift_types_summary()
        
        if languages == {'swift', 'objc'}:
            print()  # Empty line
        
        if 'objc' in languages:
            self._print_objc_types_summary()

    def _print_extension_summary(self, left_padding):
        # Display - extensions counts
        descriptions = {
            SwiftExtensionScope.FILE: '"false extensions": extensions defined for types in the same file as the extension',
            SwiftExtensionScope.PROJECT_SWIFT: 'extensions of Swift types defined somewhere else in the project',
            SwiftExtensionScope.PROJECT_OBJC: 'extensions of Objective-C types defined somewhere else in the project',
            SwiftExtensionScope.OUTER: 'extensions of types defined in standard and 3rd party libraries like Foundation UIKit, etc.',
        }

        # Counters
        extensions_by_scope = self.xcode_project.swift_extensions_grouped_by_scope
        counters = {scope: len(extensions) for scope, extensions in extensions_by_scope.items()}

        ext_max_count = max([v for v in counters.values()])
        ext_width = len(str(ext_max_count)) + left_padding + 1

        print('{:>{ext_width}} file scoped ({})'.format(counters[SwiftExtensionScope.FILE],
                                                        descriptions[SwiftExtensionScope.FILE],
                                                        ext_width=ext_width))
        print('{:>{ext_width}} project scoped Swift ({})'.format(counters[SwiftExtensionScope.PROJECT_SWIFT],
                                                                 descriptions[SwiftExtensionScope.PROJECT_SWIFT],
                                                                 ext_width=ext_width))
        print('{:>{ext_width}} project scoped Objective-C ({})'.format(counters[SwiftExtensionScope.PROJECT_OBJC],
                                                                       descriptions[SwiftExtensionScope.PROJECT_OBJC],
                                                                       ext_width=ext_width))
        print('{:>{ext_width}} outer scoped ({})'.format(counters[SwiftExtensionScope.OUTER],
                                                         descriptions[SwiftExtensionScope.OUTER],
                                                         ext_width=ext_width))

    def _print_swift_types_summary(self):
        cprint('=> Swift types', attrs=['bold'])

        # Wordings
        wordings = [
            (SwiftTypeType.CLASS, 'classes'),
            (SwiftTypeType.STRUCT, 'structs'),
            (SwiftTypeType.ENUM, 'enums'),
            (SwiftTypeType.PROTOCOL, 'protocols'),
            (SwiftTypeType.EXTENSION, 'extensions'),
        ]

        assert len(wordings) == len(SwiftTypeType.ALL)

        # Counters
        counters = dict()

        # Objc types
        objc_classes = self.xcode_project.objc_types_filtered(type_in={ObjcTypeType.CLASS})[ObjcTypeType.CLASS]
        objc_class_names = [c.name for c in objc_classes]

        # Swift types
        for swift_type_type, swift_types in self.xcode_project.swift_types_filtered().items():
            counters[swift_type_type] = len(swift_types)

        # Total
        total_types_count = len(self.xcode_project.swift_types)

        # Display
        width = len(str(total_types_count))

        for (swift_type_type, wording) in wordings:
            print('{:>{width}} {wording}'.format(counters[swift_type_type],
                                                 width=width,
                                                 wording=wording))

        self._print_extension_summary(left_padding=width)

        cprint('{:>{width}} swift types in total'.format(total_types_count, width=width), attrs=['bold'])

    def _print_objc_types_summary(self):
        cprint('=> Objective-C types', attrs=['bold'])

        # Wordings
        wordings = [
            (ObjcTypeType.CLASS, 'classes'),
            (ObjcTypeType.CATEGORY, 'categories'),
            (ObjcTypeType.ENUM, 'enums'),
            (ObjcTypeType.CONSTANT, 'constants'),
            (ObjcTypeType.PROTOCOL, 'protocols'),
        ]

        assert len(wordings) == len(ObjcTypeType.ALL)

        # Counters
        counters = dict()

        # Obj-C types
        for objc_type_type, objc_types in self.xcode_project.objc_types_filtered().items():
            counters[objc_type_type] = len(objc_types)

        # Total
        total_types_count = len(self.xcode_project.objc_types)

        # Display
        width = len(str(total_types_count))

        for (objc_type_type, wording) in wordings:
            print('{:>{width}} {wording}'.format(counters[objc_type_type],
                                                 width=width,
                                                 wording=wording))

        cprint('{:>{width}} objc types in total'.format(total_types_count, width=width), attrs=['bold'])

    def print_shared_files(self):
        # key is a file, value is a set of targets
        file_targets = dict()

        # Search targets for shared files
        for target in self.xcode_project.targets:
            for target_file in target.files:
                if target_file in file_targets:
                    file_targets[target_file].add(target)
                else:
                    file_targets[target_file] = set([target])

        # Filter files
        filepath_targets = {f.filepath: targets for (f, targets) in file_targets.items() if len(targets) >= 2}

        # Sort by filepath
        filepaths = [p for p in filepath_targets.keys()]
        filepaths.sort()

        # Sort displays
        for filepath in filepaths:
            targets = filepath_targets[filepath]
            targets_display = ', '.join([t.name for t in targets])
            print('{} [{}]'.format(filepath, targets_display))

    def print_files_summary(self):
        self._print_horizontal_line()

        source_files = set()
        resource_files = set()
        header_files = set()

        for target in self.xcode_project.targets:
            source_files |= target.source_files
            resource_files |= target.resource_files
            header_files |= target.header_files

        # Source files
        swift_source_files = set()
        objc_source_files = set()
        other_source_files = set()
        
        for source_file in source_files:
            if source_file.filepath.endswith('.swift'):
                swift_source_files.add(source_file)
            elif source_file.filepath.endswith('.m'):
                objc_source_files.add(source_file)
            else:
                other_source_files.add(source_file)

        # Counters
        source_files_count = len(source_files)

        # Counters - source files
        swift_source_files_count = len(swift_source_files)
        objc_source_files_count = len(objc_source_files)
        other_source_files_count = len(other_source_files)

        resource_files_count = len(resource_files)
        header_files_count = len(header_files)

        total_files_count = source_files_count + resource_files_count + header_files_count

        # Display
        width = len(str(total_files_count))
        max_source_file_count = max([swift_source_files_count, objc_source_files_count, other_source_files_count])
        src_width = len(str(max_source_file_count)) + width + 1

        print('{:>{width}} source files whose:'.format(source_files_count, width=width))
        
        print('{:>{src_width}} swift files (.swift)'.format(swift_source_files_count, src_width=src_width))
        print('{:>{src_width}} objective-C files (.m)'.format(objc_source_files_count, src_width=src_width))
        print('{:>{src_width}} other source files'.format(other_source_files_count, src_width=src_width))
        
        print('{:>{width}} resource files'.format(resource_files_count, width=width))
        print('{:>{width}} header files'.format(header_files_count, width=width))
        cprint('{:>{width}} files in total'.format(total_files_count, width=width), attrs=['bold'])
    
    def print_groups(self, filter_mode=False):
        groups = self.xcode_project.groups_filtered(filter_mode=filter_mode)
        group_paths = [g.group_path for g in groups]

        group_paths.sort()

        for group_path in group_paths:
            print(group_path)
    
    def print_all_groups_summary(self):
        self._print_horizontal_line()

        groups = self.xcode_project.groups_filtered()

        # Total groups count
        total_groups_count = len(groups)

        # Root groups count
        root_groups_count = len(self.xcode_project.groups)
        variant_root_groups_count = len([g for g in self.xcode_project.groups if g.is_variant])

        # Non root groups count
        variant_groups_count = len([g for g in groups if g.is_variant]) - variant_root_groups_count
        other_groups_count = total_groups_count - root_groups_count - variant_groups_count

        print('{:>2} Root groups (whom {} variant)'.format(root_groups_count, variant_root_groups_count))
        print('{:>2} Variant groups'.format(variant_groups_count))
        print('{:>2} Other groups'.format(other_groups_count))
        cprint('{:>2} Groups in total'.format(total_groups_count), attrs=['bold'])
    
    def _find_folder_filepaths(self, ignored_dirpaths, ignored_dirs, ignored_files={'.DS_Store'}):
        folder_filepaths = set()

        for (dirpath, dirnames, filenames) in os.walk(self.xcode_project.dirpath):
            relative_dirpath = dirpath[len(self.xcode_project.dirpath):]
            folder_parts = relative_dirpath.split(os.path.sep)

            # Filter folder to ignore by path
            continue_to_next_dirpath = False
            for ignored_dirpath in ignored_dirpaths:
                if relative_dirpath.startswith(ignored_dirpath):
                    continue_to_next_dirpath = True
                    break
            if continue_to_next_dirpath:
                continue

            # Filter folder to ignore by name
            if ignored_dirs & set(folder_parts):
                continue
            
            # Filter xcodeproj itself
            if '.xcodeproj' in relative_dirpath:
                continue
            
            # Filter xcworkspace
            if '.xcworkspace' in relative_dirpath:
                continue
            
            # Detect xcassets folders
            if relative_dirpath.endswith('.xcassets'):
                folder_filepaths.add(relative_dirpath)

            elif '.xcassets' in relative_dirpath:
                # Ignore Subfolder of a xcasset folder
                pass

            # Detect xcstickers folders
            elif relative_dirpath.endswith('.xcstickers'):
                folder_filepaths.add(relative_dirpath)

            # Ignore Subfolder of a xcstickers folder
            elif '.xcstickers' in relative_dirpath:
                pass

            # Add as file folder considered as file by Xcode,
            # and don not add its inner files.
            elif folder_parts[-1].endswith('.bundle'):
                folder_filepaths.add(relative_dirpath)
            
            # Filter folder inside folder considered as files (by Xcode)
            elif [p for p in folder_parts if p.endswith('.bundle')]:
                continue

            else:
                for filename in filenames:
                    if filename not in ignored_files:
                        folder_filepaths.add('{}/{}'.format(relative_dirpath, filename))
        
        return folder_filepaths

    def print_orphan_files(self, ignored_dirpaths, ignored_dirs, mode):
        # Folder's filepaths
        folder_filepaths = self._find_folder_filepaths(ignored_dirpaths, ignored_dirs)

        # Orphan filepaths
        if mode == 'all':
            target_filepaths = {f.filepath for f in self.xcode_project.target_files}
            filepaths = list(folder_filepaths - target_filepaths)
        
        elif mode == 'project':
            project_filepaths = {f.filepath for f in self.xcode_project.files}
            filepaths = list(folder_filepaths - project_filepaths)
        
        elif mode == 'target':
            target_less_files = self.xcode_project.files - self.xcode_project.target_files
            filepaths = []

            for target_file in target_less_files:
                # In this mode we ignore .h files and Info.plist files
                if target_file.filepath.endswith('Info.plist'):
                    continue
                
                if target_file.filepath.endswith('.h'):
                    continue
                
                # Filter ignored dirpaths
                ignore_current_file = False
                for ignored_dirpath in ignored_dirpaths:
                    if target_file.filepath.startswith(ignored_dirpath):
                        ignore_current_file = True
                        break
                if ignore_current_file:
                    continue

                # Filter folder to ignore by name
                folder_parts = target_file.filepath.split('/')[:-1]
                if ignored_dirs & set(folder_parts):
                    continue
            
                filepaths.append(target_file.filepath)
        
        elif mode == 'referenced':
            # Get all '*.Info.plist' and '*.h' files from target files
            filepaths = []
            for target_file in self.xcode_project.target_files:
                if not target_file.filepath.endswith('Info.plist') \
                    and not target_file.filepath.endswith('.h'):
                    continue
                filepaths.append(target_file.filepath)
        
        elif mode == 'unreferenced':
            # Get all '*.Info.plist' and '*.h' files project's target less files set
            filepaths = []
            for target_file in self.xcode_project.target_less_files:
                if not target_file.filepath.endswith('Info.plist') \
                    and not target_file.filepath.endswith('.h'):
                    continue
                filepaths.append(target_file.filepath)

        else:
            raise ValueError("Not supported orphan mode: '{}'.".format(mode))
        
        # Sort filepaths
        filepaths.sort()

        for filepath in filepaths:
            print(filepath)
    
    def print_nonregular_files(self):
        # Sort by filepath the results
        file_group_paths = dict()

        for group_file, group in self.xcode_project.nonregular_files:
            file_group_paths[group_file.filepath] = group.group_path
        
        filepaths = list(file_group_paths.keys())
        filepaths.sort()

        # Display filepaths and group paths
        for filepath in filepaths:
            print("{} [{}]".format(filepath, file_group_paths[filepath]))

    def _print_missing_objc_files_summary(self,
                                          duplicate_h_file_names,
                                          duplicate_m_file_names,
                                          missing_h_file_names,
                                          missing_m_file_names):
        total_count = len(duplicate_h_file_names) + len(duplicate_m_file_names) \
            + len(missing_h_file_names) + len(missing_m_file_names)

        width = len(str(total_count))

        print('{:>{width}} duplicate .h file names'.format(len(duplicate_h_file_names), width=width))
        print('{:>{width}} duplicate .m file names'.format(len(duplicate_m_file_names), width=width))
        print('{:>{width}} missing .h file names'.format(len(missing_h_file_names), width=width))
        print('{:>{width}} missing .m file names'.format(len(missing_m_file_names), width=width))

        cprint('{:>{width}} duplicate or missing file names in total'.format(total_count, width=width), attrs=['bold'])


    def print_missing_objc_files(self):
        duplicate_h_file_names = set()
        duplicate_m_file_names = set()

        h_file_names = set()
        m_file_names = set()

        for objc_file in self.xcode_project.objc_files:
            filename = objc_file.filepath.split('/')[-1]
            base_filename = filename[:-2]  # filename without extension

            if filename.endswith('.h'):
                # Find duplicate name
                if base_filename in h_file_names:
                    duplicate_h_file_names.add(base_filename)

                h_file_names.add(base_filename)
            
            if filename.endswith('.m'):
                # Find duplicate name
                if base_filename in m_file_names:
                    duplicate_m_file_names.add(base_filename)

                m_file_names.add(base_filename)
        
        # .h files with same names
        duplicate_h_file_names_list = list(duplicate_h_file_names)
        duplicate_h_file_names_list.sort()
        for duplicate_h_file_name in duplicate_h_file_names_list:
            print("[Duplicate .h file name] {}.h".format(duplicate_h_file_name))

        # .m files with same names
        duplicate_m_file_names_list = list(duplicate_m_file_names)
        duplicate_m_file_names_list.sort()
        for duplicate_m_file_name in duplicate_m_file_names_list:
            print("[Duplicate .m file name] {}.m".format(duplicate_m_file_name))

        # .m files missing .h files
        missing_h_file_names = list(m_file_names - h_file_names)
        missing_h_file_names.sort()
        for missing_h_file_name in missing_h_file_names:
            print("[Missing .h file] {}.h".format(missing_h_file_name))

        # .h files missing .m files
        missing_m_file_names = list(h_file_names - m_file_names)
        missing_m_file_names.sort()
        for missing_m_file_name in missing_m_file_names:
            print("[Missing .m file] {}.h".format(missing_m_file_name))

        # Summary

        self._print_horizontal_line()

        self._print_missing_objc_files_summary(duplicate_h_file_names=duplicate_h_file_names_list,
                                               duplicate_m_file_names=duplicate_m_file_names_list,
                                               missing_h_file_names=missing_h_file_names,
                                               missing_m_file_names=missing_m_file_names)