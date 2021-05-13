from udapi.core.block import Block
import udapi.core.coref
from udapi.block.write.textmodetreeshtml import TextModeTreesHtml
from udapi.block.write.textmodetrees import TextModeTrees

class PrintMentions(Block):
    """Print mentions with various properties."""

    def __init__(self, continuous='include', almost_continuous='include', treelet='include',
                 forest='include', almost_forest='include', oneword='include', singleton='include',
                 empty='include', max_trees=100, html=False,
                 print_sent_id=True, print_text=True, add_empty_line=True, indent=1,
                 minimize_cross=True, color=True, attributes='form,upos,deprel',
                 print_undef_as='_', print_doc_meta=True, print_comments=False,
                 mark='(Mark)', hints=True, layout='classic',
                 **kwargs):
        super().__init__(**kwargs)
        self.continuous = self._convert(continuous)
        self.almost_continuous = self._convert(almost_continuous)
        self.treelet = self._convert(treelet)
        self.forest = self._convert(forest)
        self.almost_forest = self._convert(almost_forest)
        self.oneword = self._convert(oneword)
        self.singleton = self._convert(singleton)
        self.empty = self._convert(empty)

        self.max_trees = max_trees
        self.html = html
        print_class = TextModeTreesHtml if html else TextModeTrees
        self.print_block = print_class(
                print_sent_id=print_sent_id, print_text=print_text, add_empty_line=add_empty_line, indent=indent,
                minimize_cross=minimize_cross, color=color, attributes=attributes,
                print_undef_as=print_undef_as, print_doc_meta=print_doc_meta, print_comments=print_comments,
                mark=mark, hints=hints, layout=layout)

    def _convert(self, value):
        if value in {'include', 'exclude', 'only'}:
            return value
        if value == 1:
            return 'only'
        if value == 0:
            return 'exclude'
        raise ValueError('unknown value ' + value)

    def before_process_document(self, document):
        self.print_block.before_process_document(document)

    def after_process_document(self, document):
        self.print_block.after_process_document(document)

    def _ok(self, condition, value):
        if value == 'include':
            return True
        return (condition and value == 'only') or (not condition and value=='exclude')

    def _is_auxiliary(self, node):
        if node.udeprel in {'case', 'cc', 'punct', 'conj', 'mark', 'appos', 'cop', 'aux'}:
            return True
        if node.udeprel == 'dep' and node.upos in {'ADP', 'SCONJ', 'CCONJ'}:
            return True
        return False

    def _is_forest(self, mention, mwords, almost):
        for w in mention.words:
            for ch in w.children():
                if ch not in mwords:
                    if not almost:
                        return False
                    if not (w.parent and w.parent not in mwords and self._is_auxiliary(ch)):
                        return False
        return True

    def _is_almost_continuous(self, mention):
        if ',' not in mention.span:
            return True
        nonempty = [w for w in mention.words if not w.is_empty()]
        if not nonempty:
            return True
        mwords = set(mention.words)
        gap_nodes = [w for w in mention.head.root.descendants if w > nonempty[0] and w < nonempty[-1] and not w in mwords]
        for gap_node in gap_nodes:
            if not gap_node.is_empty():
                return False
        return True

    def process_document(self, doc):
        printed_trees = 0
        for cluster in doc.coref_clusters.values():
            if not self._ok(len(cluster.mentions) == 1, self.singleton):
                continue

            for mention in cluster.mentions:
                if not self._ok(len(mention.words) == 1, self.oneword):
                    continue
                if not self._ok(',' not in mention.span, self.continuous):
                    continue
                if self.almost_continuous != 'include' and not self._ok(self._is_almost_continuous(mention), self.almost_continuous):
                    continue

                empty_mwords = [w for w in mention.words if w.is_empty()]
                if not self._ok(len(empty_mwords) > 0, self.empty):
                    continue

                heads, mwords = 0, set(mention.words)
                for w in mention.words:
                    if w.parent:
                        heads += 0 if w.parent in mwords else 1
                    else:
                        heads += 0 if any(d['parent'] in mwords for d in w.deps) else 1
                if not self._ok(heads <= 1, self.treelet):
                    continue
                if self.forest != 'include' and not self._ok(self._is_forest(mention, mwords, False), self.forest):
                    continue
                if self.almost_forest != 'include' and not self._ok(self._is_forest(mention, mwords, True), self.almost_forest):
                    continue

                for w in mention.words:
                    w.misc['Mark'] = 1
                if self.max_trees:
                    printed_trees += 1
                    if printed_trees > self.max_trees:
                        return
                    #print(f"{printed_trees}/{self.max_trees}")
                self.print_block.process_tree(mention.head.root)
                for w in mention.words:
                    del w.misc['Mark']
