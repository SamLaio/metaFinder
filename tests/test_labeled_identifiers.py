from bs4 import BeautifulSoup
from metafinder.models import BookMetadata
from metafinder.sources.generic import GenericPageParser


def test_eisbn_label_moves_misclassified_jsonld_isbn_without_losing_paper():
    metadata=BookMetadata(isbn="9786269754168")
    evidence=[]
    soup=BeautifulSoup("<p>ISBN：9786269754175</p><p>EISBN (EPUB)：9786269754168</p>","html.parser")
    GenericPageParser()._from_visible_labels(soup,metadata,evidence)
    assert metadata.isbn=="9786269754175"
    assert metadata.eisbn=="9786269754168"
    assert "visible-labels" in evidence


def test_person_labels_in_book_title_are_not_people():
    soup = BeautifulSoup('<title>鋼索上的譯者：翻譯如何引發戰火</title><h1>作者：一段小說</h1><p>譯者：黃翎</p>', 'html.parser')
    metadata = BookMetadata()
    GenericPageParser()._from_visible_labels(soup, metadata, [])
    assert metadata.translators == ['黃翎']


def test_subtitle_without_a_translator_label_stays_empty():
    soup = BeautifulSoup('<title>鋼索上的譯者：翻譯如何引發戰火</title>', 'html.parser')
    metadata = BookMetadata()
    GenericPageParser()._from_visible_labels(soup, metadata, [])
    assert metadata.translators == []
