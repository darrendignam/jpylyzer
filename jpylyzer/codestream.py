#! /usr/bin/env python3
"""
JPEG 2000 codestream validation
"""

from __future__ import division
from . import etpatch as ET
from .validator import Validator
from .tilepart import TilePartValidator
from .csmarkers import CSMarkerValidator


class CSValidator(Validator):
    """Validator class for JPEG 2000 codestream
    """

    def __init__(self, options, bType, boxContents,
                 startOffset=None, components=None):
        """Initialise a codestream validator."""
        Validator.__init__(self, options, bType, boxContents,
                           startOffset=None, components=None)
        self.options = options
        self.format = self.options['validationFormat']
        self.verboseFlag = self.options['verboseFlag']
        self.nullxmlFlag = self.options['nullxmlFlag']
        self.packetmarkersFlag = self.options['packetmarkersFlag']
        self.boxType = "codestream"
        if self.format in ['j2c', 'jhc']:
            self.characteristics = ET.Element("properties")
            self.tests = ET.Element("tests")
            self.warnings = ET.Element("warnings")
        else:
            self.characteristics = ET.Element(self.boxType)
            self.tests = ET.Element(self.boxType)
            self.warnings = ET.Element(self.boxType)
        self.boxContents = boxContents
        self.startOffset = startOffset
        self.returnOffset = None
        self.isValid = None
        self.tilePartLength = None
        self.csiz = components
        self.bTypeString = bType

    # Validator function for JPEG 2000 codestream

    def _startOfData(self, offset):
        """Offset of the first byte after the SOD marker of the tile-part that
        starts at offset, or the end of the codestream if there is no SOD."""
        offset += 12
        while offset < len(self.boxContents):
            marker, _, _, offsetNext = self._getMarkerSegment(offset)
            if marker == b'\xff\x93':
                return offset + 2
            if offsetNext <= offset:
                break
            offset = offsetNext
        return len(self.boxContents)

    def _tilesWithSamples(self, numberOfTiles):
        """Indices of the tiles that have at least one non-empty tile-component
        (ISO/IEC 15444-1 Equations B-7 to B-12). Falls back to all tiles if
        the SIZ values cannot be used or give an empty image area."""
        siz = self.characteristics.find('siz')
        allTiles = set(range(numberOfTiles))
        if siz is None:
            return allTiles
        names = ['xsiz', 'ysiz', 'xOsiz', 'yOsiz', 'xTsiz', 'yTsiz', 'xTOsiz', 'yTOsiz']
        xsiz, ysiz, xOsiz, yOsiz, xTsiz, yTsiz, xTOsiz, yTOsiz = [
            siz.findElementText(name) for name in names]
        separations = list(zip(siz.findAllText('xRsiz'), siz.findAllText('yRsiz')))
        values = [xsiz, ysiz, xOsiz, yOsiz, xTsiz, yTsiz, xTOsiz, yTOsiz]
        if (not separations or any(not isinstance(v, int) or v < 0 for v in values)
                or xTsiz == 0 or yTsiz == 0 or xsiz <= xTOsiz
                or xOsiz >= xsiz or yOsiz >= ysiz
                or any(not isinstance(r, int) or r <= 0 for pair in separations for r in pair)):
            return allTiles

        tilesX = -(-(xsiz - xTOsiz) // xTsiz)
        tilesWithSamples = set()
        for tile in allTiles:
            p, q = tile % tilesX, tile // tilesX
            tx0 = max(xTOsiz + p * xTsiz, xOsiz)
            tx1 = min(xTOsiz + (p + 1) * xTsiz, xsiz)
            ty0 = max(yTOsiz + q * yTsiz, yOsiz)
            ty1 = min(yTOsiz + (q + 1) * yTsiz, ysiz)
            # Ceiling division: tcx0 = ceil(tx0 / XRsiz) etc.
            if any(-(-tx1 // xRsiz) > -(-tx0 // xRsiz) and
                   -(-ty1 // yRsiz) > -(-ty0 // yRsiz)
                   for xRsiz, yRsiz in separations):
                tilesWithSamples.add(tile)
        return tilesWithSamples

    def validate_codestream(self):
        """Validate JPEG 2000 codestream"""
        # Codestream length
        length = len(self.boxContents)

        # Keep track of byte offsets
        offset = 0

        # Number of PLM and PPM markers
        plmCount = 0
        ppmCount = 0

        # Read first marker segment. This must be the start-of-codestream
        # marker
        marker, _, segContents, offsetNext = self._getMarkerSegment(offset)

        # Marker must be start-of-codestream marker
        self.testFor("codestreamStartsWithSOCMarker", marker == b'\xff\x4f')
        offset = offsetNext

        # Read next marker segment. This must be the SIZ (image and tile
        # size) marker
        marker, _, segContents, offsetNext = self._getMarkerSegment(offset)
        foundSIZMarker = marker == b'\xff\x51'
        self.testFor("foundSIZMarker", foundSIZMarker)

        if foundSIZMarker:
            # Validate SIZ segment
            resultsSIZ = CSMarkerValidator(
                self.options,
                marker,
                segContents).validate()
            testsSIZ = resultsSIZ.tests
            characteristicsSIZ = resultsSIZ.characteristics
            warningsSIZ = resultsSIZ.warnings

            self.tests.appendIfNotEmpty(testsSIZ)
            self.characteristics.append(characteristicsSIZ)
            self.warnings.appendIfNotEmpty(warningsSIZ)
            # Get csiz value, which is needed later on by the COC validation
            # function
            csiz = characteristicsSIZ.findElementText('csiz')

            offset = offsetNext

            # Loop through remaining marker segments in main header; first SOT (start of
            # tile-part marker) indicates end of main header.

            # Initial values for marker found flags
            foundPRFMarker = False
            foundCPFMarker = False
            foundCAPMarker = False
            foundCODMarker = False
            foundQCDMarker = False

            while marker != b'\xff\x90' and offsetNext != -9999:
                marker, _, segContents, offsetNext = self._getMarkerSegment(offset)

                if marker == b'\xff\x52':
                    # COD (coding style default) marker segment
                    # COD is required
                    foundCODMarker = True
                    # Validate COD segment
                    resultsCOD = CSMarkerValidator(
                        self.options,
                        marker,
                        segContents).validate()
                    testsCOD = resultsCOD.tests
                    characteristicsCOD = resultsCOD.characteristics
                    warningsCOD = resultsCOD.warnings
                    self.tests.appendIfNotEmpty(testsCOD)
                    self.characteristics.append(characteristicsCOD)
                    self.warnings.appendIfNotEmpty(warningsCOD)
                    offset = offsetNext

                elif marker == b'\xff\x53':
                    # COC (coding style component) marker segment
                    # COC is optional
                    # Validate COC segment
                    resultsCOC = CSMarkerValidator(
                        self.options,
                        marker,
                        segContents,
                        components=csiz).validate()
                    testsCOC = resultsCOC.tests
                    characteristicsCOC = resultsCOC.characteristics
                    warningsCOC = resultsCOC.warnings
                    self.tests.appendIfNotEmpty(testsCOC)
                    self.characteristics.append(characteristicsCOC)
                    self.warnings.appendIfNotEmpty(warningsCOC)
                    offset = offsetNext

                elif marker == b'\xff\x5c':
                    # QCD (quantization default) marker segment
                    # QCD is required
                    foundQCDMarker = True
                    # Validate QCD segment
                    resultsQCD = CSMarkerValidator(
                        self.options,
                        marker,
                        segContents).validate()
                    testsQCD = resultsQCD.tests
                    characteristicsQCD = resultsQCD.characteristics
                    warningsQCD = resultsQCD.warnings
                    self.tests.appendIfNotEmpty(testsQCD)
                    self.characteristics.append(characteristicsQCD)
                    self.warnings.appendIfNotEmpty(warningsQCD)
                    offset = offsetNext

                elif marker == b'\xff\x5d':
                    # QCC (quantization component) marker segment
                    # QCC is optional
                    # Validate QCC segment
                    resultsQCC = CSMarkerValidator(
                        self.options,
                        marker,
                        segContents,
                        components=csiz).validate()
                    testsQCC = resultsQCC.tests
                    characteristicsQCC = resultsQCC.characteristics
                    warningsQCC = resultsQCC.warnings
                    self.tests.appendIfNotEmpty(testsQCC)
                    self.characteristics.append(characteristicsQCC)
                    self.warnings.appendIfNotEmpty(warningsQCC)
                    offset = offsetNext

                elif marker == b'\xff\x5e':
                    # RGN (region of interest) marker segment
                    # RGN is optional
                    # Validate RGN segment
                    resultsRGN = CSMarkerValidator(
                        self.options,
                        marker,
                        segContents,
                        components=csiz).validate()
                    testsRGN = resultsRGN.tests
                    characteristicsRGN = resultsRGN.characteristics
                    warningsRGN = resultsRGN.warnings
                    self.tests.appendIfNotEmpty(testsRGN)
                    self.characteristics.append(characteristicsRGN)
                    self.warnings.appendIfNotEmpty(warningsRGN)
                    offset = offsetNext

                elif marker == b'\xff\x5f':
                    # POC (progression order change) marker segment
                    # POC is optional
                    # Validate QCC segment
                    resultsPOC = CSMarkerValidator(
                        self.options,
                        marker,
                        segContents,
                        components=csiz).validate()
                    testsPOC = resultsPOC.tests
                    characteristicsPOC = resultsPOC.characteristics
                    warningsPOC = resultsPOC.warnings
                    self.tests.appendIfNotEmpty(testsPOC)
                    self.characteristics.append(characteristicsPOC)
                    self.warnings.appendIfNotEmpty(warningsPOC)
                    offset = offsetNext

                elif marker == b'\xff\x63':
                    # CRG (component registration) marker segment
                    # Validate CRG segment
                    resultsCRG = CSMarkerValidator(
                        self.options,
                        marker,
                        segContents,
                        components=csiz).validate()
                    testsCRG = resultsCRG.tests
                    characteristicsCRG = resultsCRG.characteristics
                    warningsCRG = resultsCRG.warnings
                    self.tests.appendIfNotEmpty(testsCRG)
                    self.characteristics.append(characteristicsCRG)
                    self.warnings.appendIfNotEmpty(warningsCRG)
                    offset = offsetNext

                elif marker == b'\xff\x64':
                    # COM (codestream comment) marker segment
                    # Validate COM segment
                    resultsCOM = CSMarkerValidator(
                        self.options,
                        marker,
                        segContents).validate()
                    testsCOM = resultsCOM.tests
                    characteristicsCOM = resultsCOM.characteristics
                    warningsCOM = resultsCOM.warnings
                    self.tests.appendIfNotEmpty(testsCOM)
                    self.characteristics.append(characteristicsCOM)
                    self.warnings.appendIfNotEmpty(warningsCOM)
                    offset = offsetNext

                elif marker == b'\xff\x50':
                    # CAP marker
                    foundCAPMarker = True
                    resultsCAP = CSMarkerValidator(
                        self.options,
                        marker,
                        segContents).validate()
                    testsCAP = resultsCAP.tests
                    characteristicsCAP = resultsCAP.characteristics
                    warningsCAP = resultsCAP.warnings
                    self.tests.appendIfNotEmpty(testsCAP)
                    self.characteristics.append(characteristicsCAP)
                    self.warnings.appendIfNotEmpty(warningsCAP)
                    offset = offsetNext

                elif marker == b'\xff\x56':
                    # PRF marker
                    foundPRFMarker = True
                    resultsPRF = CSMarkerValidator(
                        self.options,
                        marker,
                        segContents).validate()
                    testsPRF = resultsPRF.tests
                    characteristicsPRF = resultsPRF.characteristics
                    warningsPRF = resultsPRF.warnings
                    self.tests.appendIfNotEmpty(testsPRF)
                    self.characteristics.append(characteristicsPRF)
                    self.warnings.appendIfNotEmpty(warningsPRF)
                    offset = offsetNext

                elif marker == b'\xff\x59':
                    # CPF marker
                    foundCPFMarker = True
                    resultsCPF = CSMarkerValidator(
                        self.options,
                        marker,
                        segContents).validate()
                    testsCPF = resultsCPF.tests
                    characteristicsCPF = resultsCPF.characteristics
                    warningsCPF = resultsCPF.warnings
                    self.tests.appendIfNotEmpty(testsCPF)
                    self.characteristics.append(characteristicsCPF)
                    self.warnings.appendIfNotEmpty(warningsCPF)
                    offset = offsetNext

                elif marker == b'\xff\x90':
                    # Start of tile (SOT) marker segment; don't update offset as this
                    # will get us of out of this loop (for functional
                    # readability):
                    pass

                elif marker == b'\xff\x55':
                    # TLM marker
                    resultsTLM = CSMarkerValidator(
                        self.options,
                        marker,
                        segContents).validate()
                    testsTLM = resultsTLM.tests
                    characteristicsTLM = resultsTLM.characteristics
                    warningsTLM = resultsTLM.warnings
                    self.tests.appendIfNotEmpty(testsTLM)
                    self.characteristics.append(characteristicsTLM)
                    self.warnings.appendIfNotEmpty(warningsTLM)
                    offset = offsetNext

                elif marker == b'\xff\x57':
                    # PLM marker
                    plmCount += 1
                    resultsPLM = CSMarkerValidator(
                        self.options,
                        marker,
                        segContents).validate()
                    testsPLM = resultsPLM.tests
                    characteristicsPLM = resultsPLM.characteristics
                    warningsPLM = resultsPLM.warnings
                    self.tests.appendIfNotEmpty(testsPLM)
                    if self.packetmarkersFlag:
                        self.characteristics.append(characteristicsPLM)
                    self.warnings.appendIfNotEmpty(warningsPLM)
                    offset = offsetNext

                elif marker == b'\xff\x60':
                    # PPM marker
                    ppmCount += 1
                    resultsPPM = CSMarkerValidator(
                        self.options,
                        marker,
                        segContents).validate()
                    testsPPM = resultsPPM.tests
                    characteristicsPPM = resultsPPM.characteristics
                    warningsPPM = resultsPPM.warnings
                    self.tests.appendIfNotEmpty(testsPPM)
                    if self.packetmarkersFlag:
                        self.characteristics.append(characteristicsPPM)
                    self.warnings.appendIfNotEmpty(warningsPPM)
                    offset = offsetNext

                else:
                    # Any other marker segment: ignore and move on to next one
                    # Note that this should result in validation error as all
                    # marker segments are covered above!!
                    offset = offsetNext

            # Add ppmCount and plmCount value to characteristics
            self.addCharacteristic("ppmCount", ppmCount)
            self.addCharacteristic("plmCount", plmCount)

            # Add foundCODMarker / foundQCDMarker outcome to tests
            self.testFor("foundCODMarker", foundCODMarker)
            self.testFor("foundQCDMarker", foundQCDMarker)

            # Test for presence of CAP marker if rsiz indicates capabilities that
            # are defined there
            rsiz = self.characteristics.findElementText(
                'siz/rsiz')
            # Two most significant bits of rsiz indicate CAP marker use
            if (rsiz >> 14) & 15 == 1:
                self.testFor("foundCAPMarker", foundCAPMarker)

            # Remainder of codestream is a sequence of tile parts, followed by one
            # end-of-codestream marker

            # Expected number of tiles (as calculated from info in SIZ marker)
            numberOfTilesExpected = self.characteristics.findElementText(
                'siz/numberOfTiles')

            # If we did not get the number of tiles, assume it is zero
            if not numberOfTilesExpected:
                numberOfTilesExpected = 0

            # Impose upper limit on numberOfTilesExpected to avoid misbehaviour
            # in case of corrupted files. Value of 65535 equals upper value imposed by Kakadu
            # (can't find this  anywhere the standard though)
            numberOfTilesExpected = min(numberOfTilesExpected, 65535)

            # Set of the indices of all tiles found
            tileIndices = set()

            # Dictionary that contains expected number of tile parts for each
            # tile
            tilePartsPerTileExpected = {}

            # Dictionary that contains found number of tile parts for each tile
            tilePartsPerTileFound = {}

            # Create entry for each tile part and initialise value at 0
            for i in range(numberOfTilesExpected):
                tilePartsPerTileFound[i] = 0

            # Tile-part indices must be 0, 1, 2, ... for each tile in codestream
            # order, and all non-zero tnsot values of a tile must be the same
            # (ISO/IEC 15444-1 Section A.4.2)
            tilePartIndicesInOrder = True
            tnsotValuesPerTile = {}

            # Only the last tile-part in the codestream may have psot = 0
            foundPsotZero = False

            # Create sub-elements to store tile-part characteristics, tests and warnings
            tilePartCharacteristics = ET.Element('tileParts')
            tilePartTests = ET.Element('tileParts')
            tilePartWarnings = ET.Element('tileParts')

            while marker == b'\xff\x90':
                marker = self.boxContents[offset:offset + 2]

                if marker == b'\xff\x90':
                    resultsTilePart = TilePartValidator(
                        self.options,
                        marker,
                        self.boxContents,
                        startOffset=offset,
                        components=csiz).validate()
                    testsTilePart = resultsTilePart.tests
                    characteristicsTilePart = resultsTilePart.characteristics
                    warningsTilePart = resultsTilePart.warnings
                    offsetNext = resultsTilePart.returnOffset
                    tilePartTests.appendIfNotEmpty(testsTilePart)
                    tilePartCharacteristics.append(characteristicsTilePart)
                    tilePartWarnings.appendIfNotEmpty(warningsTilePart)
                    tileIndex = characteristicsTilePart.findElementText(
                        'sot/isot')
                    tilePartIndex = characteristicsTilePart.findElementText(
                        'sot/tpsot')
                    tilePartsOfTile = characteristicsTilePart.findElementText(
                        'sot/tnsot')
                    tileIndices.add(tileIndex)
                    # Expected number of tile-parts for each tile to dictionary
                    if tilePartsOfTile != 0:
                        tilePartsPerTileExpected[tileIndex] = tilePartsOfTile
                        tnsotValuesPerTile.setdefault(tileIndex, set()).add(tilePartsOfTile)

                    if tilePartIndex != tilePartsPerTileFound.get(tileIndex, 0):
                        tilePartIndicesInOrder = False

                    # Increase found number of tile-parts for this tile by 1
                    try:
                        tilePartsPerTileFound[
                            tileIndex] = tilePartsPerTileFound[tileIndex] + 1
                    except KeyError:
                        # Tile index outside the tile grid (reported by
                        # foundExpectedNumberOfTiles): the remaining tile-parts
                        # cannot be trusted either
                        break

                    if offsetNext != offset:
                        offset = offsetNext
                    else:
                        # offsetNext same as offset: psot is 0, so this tile-part
                        # extends to the EOC marker
                        foundPsotZero = True
                        break

            # Every tile with samples must be present, and every tile found must
            # be in the tile grid. Tiles whose tile-components are all empty
            # carry no data and may be left out (e.g. conformance codestream
            # b2_mono.j2c of ISO/IEC 15444-4)
            self.testFor("foundExpectedNumberOfTiles",
                         self._tilesWithSamples(numberOfTilesExpected) <= tileIndices
                         <= set(range(numberOfTilesExpected)))

            self.testFor("tilePartIndicesConsistencyCheck", tilePartIndicesInOrder)
            self.testFor("tnsotConsistencyCheck",
                         all(len(values) == 1 for values in tnsotValuesPerTile.values()))

            if foundPsotZero:
                # No other tile-part may follow. Marker code 0xFF90 cannot occur
                # in packet headers or coded data (ISO/IEC 15444-1 Annex B and D),
                # so a SOT marker after the start of the bit stream means one does
                self.testFor("psotZeroOnlyInLastTilePart",
                             self.boxContents[self._startOfData(offset):length - 2]
                             .find(b'\xff\x90') == -1)
            else:
                # EOC must directly follow the last tile-part (ISO/IEC 15444-1
                # Section A.4.4: EOC shall be the last marker in a codestream)
                self.testFor("foundEOCAfterLastTilePart", offset == length - 2)

            # Found numbers of tile parts must match expected for every tile whose
            # tnsot is not 0 (0: number of tile-parts not given)
            if tilePartsPerTileExpected:
                self.testFor("foundExpectedNumberOfTileParts",
                             all(tilePartsPerTileFound.get(tile) == count
                                 for tile, count in tilePartsPerTileExpected.items()))

            # Add tile-part tests, characteristics and warnings to tree
            self.tests.appendIfNotEmpty(tilePartTests)
            self.characteristics.append(tilePartCharacteristics)
            self.warnings.appendIfNotEmpty(tilePartWarnings)

            # Test if all ccoc values at main header level are unique
            # (A.6.2 - no more than one COC per any given component)
            ccocElementsMain = self.characteristics.findall('coc/ccoc')
            # List with all ccoc values
            ccocValuesMain = []
            for elt in ccocElementsMain:
                ccocValuesMain.append(elt.text)

            if ccocValuesMain:
                self.testFor(
                    "maxOneCcocPerComponentMain", len(
                        set(ccocValuesMain)) == len(ccocValuesMain))

            # Test if all cqcc values at main header level are unique
            # (A.6.5 - no more than one QCC per any given component)
            cqccElementsMain = self.characteristics.findall('qcc/cqcc')
            # List with all cqcc values
            cqccValuesMain = []
            for elt in cqccElementsMain:
                cqccValuesMain.append(elt.text)
            if cqccValuesMain:
                self.testFor(
                    "maxOneCqccPerComponentMain", len(
                        set(cqccValuesMain)) == len(cqccValuesMain))

            # Test if ccoc and cqcc values are consecutive numbers
            self.testFor("ccocValuesConsecutive", self._consecutive(ccocValuesMain))
            self.testFor("cqccValuesConsecutive", self._consecutive(cqccValuesMain))

            # Consistency tests on TLM marker segments
            if len(self.characteristics.findall('tlm')) > 0:
                # Test if sum of tpCount values from TLM marker segments
                # corresponds to actual number of tile parts

                # Tile part count from jpylyzer parsing
                tpCount = len(self.characteristics.findall('tileParts/tilePart'))

                # Tile part count from TLM
                tpCountTlm = 0
                tpCountElements = self.characteristics.findall('tlm/tpCount')
                for i in range(len(tpCountElements)):
                    tpCountTlm += tpCountElements[i].text

                self.testFor("tilePartsTLMConsistencyCheck", tpCountTlm == tpCount)

                # Test if tile part lengths defined by ptlm values in TLM marker segments
                # correspond to psot values in SOT marker segments
                ptlmElements = self.characteristics.findall('tlm/ptlm')
                psotElements = self.characteristics.findall('tileParts/tilePart/sot/psot')

                # Lists of all ptlm and psot values
                ptlms = []
                for i in range(len(ptlmElements)):
                    ptlms.append(ptlmElements[i].text)
                psots = []
                for i in range(len(psotElements)):
                    psots.append(psotElements[i].text)

                self.testFor("tilePartLengthsConsistencyCheck", ptlms == psots)

            # Last 2 bytes must be end-of-codestream marker
            self.testFor("foundEOCMarker",
                         self.boxContents[length - 2:length] == b'\xff\xd9')

            if self.format in ['j2c', 'jhc'] and foundSIZMarker:

                # Calculate compression ratio
                ssizDepthValues = characteristicsSIZ.findAllText('ssizDepth')
                ysiz = characteristicsSIZ.findElementText('ysiz')
                yOsiz = characteristicsSIZ.findElementText('xOsiz')
                xsiz = characteristicsSIZ.findElementText('xsiz')
                xOsiz = characteristicsSIZ.findElementText('xOsiz')

                compressionRatio = self._calculateCompressionRatio(length,
                                                                   ssizDepthValues,
                                                                   (ysiz - yOsiz),
                                                                   (xsiz - xOsiz))
                compressionRatio = round(compressionRatio, 2)
                self.addCharacteristic("compressionRatio", compressionRatio)

        # Valid codestream only if all tests returned True
        self.isValid = self._isValid()
