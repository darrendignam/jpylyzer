#! /usr/bin/env python3
"""
Validation of JPEG 2000 codestream marker segments
"""

from __future__ import division
import math
from . import etpatch as ET
from . import byteconv as bc
from .validator import Validator


# Largest integer that every XML Schema processor accepts as xs:integer
MAX_REPORTED_INTEGER = 2 ** 63 - 1


class CSMarkerValidator(Validator):
    """Validator class for codestream marker segments
    Note that the 'boxType' variable actually represents
    marker types in the context of this class
    """

    def __init__(self, options, bType, boxContents,
                 startOffset=None, components=None):
        """Initialise a CSMarkerValidator."""
        Validator.__init__(self, options, bType, boxContents,
                           startOffset=None, components=None)
        self.options = options
        self.format = self.options['validationFormat']
        self.verboseFlag = self.options['verboseFlag']
        self.nullxmlFlag = self.options['nullxmlFlag']
        self.packetmarkersFlag = self.options['packetmarkersFlag']
        if bType in self.markerTypeMap:
            self.boxType = self.markerTypeMap[bType]

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

    # Validator functions for codestream markers and marker segments

    @staticmethod
    def _codeBlockSize(exponent):
        """Code-block width or height for its exponent (stored offset + 2), or
        -9999 if the exponent could not be read from a truncated segment or is
        outside the allowed range 2-10 (a stored 255 would otherwise give a
        78-digit number, which some XML schema validators reject)."""
        if not 2 <= exponent <= 10:
            return -9999
        return 2 ** exponent

    def validate_siz(self):
        """Image and tile size (SIZ) header fields (ISO/IEC 15444-1 Section A.5.1;
        ISO/IEC 15444-15 Section A.2)."""
        # Length of main image header
        lsiz = bc.bytesToUShortInt(self.boxContents[0:2])
        self.addCharacteristic("lsiz", lsiz)

        # lsiz must be within range 41-49190
        self.testFor("lsizIsValid", 41 <= lsiz <= 49190)

        # Decoder capabilities (rsiz).
        rsiz = bc.bytesToUShortInt(self.boxContents[2:4])
        self.addCharacteristic("rsiz", rsiz)

        if self.format in ['jp2', 'j2c']:
            # For codestream that conforms to ISO/IEC 15444-1 first 4 bits are
            # 0
            self.testFor("rsizIsValid", (rsiz >> 12) & 15 == 0)
        elif self.format in ['jph', 'jhc']:
            # Second most significant bit shall be equal to 1. Note that ISO/IEC 15444-15
            # says "bit 14" as standard counts bits right to left, starting from 0)
            self.testFor(
                "rsizIsValid", bc.getBitValue(
                    rsiz, 2, wordLength=16) == 1)

        # Extendend Capabilities bits: most significant 2 bits of rsiz
        # (shift 14 right and apply bit mask)
        extendendCapabilities = (rsiz >> 14) & 15
        # Bits that define top level profile
        # (shift right 8 bits and apply bit mask)
        profile = (rsiz >> 8) & 15

        # SubLevel (shift 4 right and apply bit mask)
        subLevel = (rsiz >> 4) & 15
        # MainLevel (apply bit mask)
        mainLevel = (rsiz) & 15

        if extendendCapabilities == 1:
            capability = "CAP"
        elif extendendCapabilities == 2:
            capability = "ISO/IEC 15444-2"
        elif extendendCapabilities == 3:
            capability = "ISO/IEC 15444-2 + CAP"
        elif profile == 0:
            # These are the profiles that don't use the sub/mainlevel scheme, with
            # values that identify them in least significant byte (which was later
            # used for mainLevel)
            if mainLevel == 0:
                capability = "ISO/IEC 15444-1"
            elif mainLevel == 1:
                capability = "Profile 0"
            elif mainLevel == 2:
                capability = "Profile 1"
            elif mainLevel == 3:
                capability = "2K digital cinema profile"
            elif mainLevel == 4:
                capability = "4K digital cinema profile"
            elif mainLevel == 5:
                capability = "Scalable 2K digital cinema profile"
            elif mainLevel == 6:
                capability = "Scalable 4K digital cinema profile"
            elif mainLevel == 7:
                capability = "Long-term storage profile"
            else:
                capability = "Unknown (value not defined in ISO/IEC 15444-1)"
        elif profile == 1:
            capability = "Broadcast Contribution Single Tile Profile, Mainlevel " + \
                str(mainLevel)
        elif profile == 2:
            capability = "Broadcast Contribution Multi-tile Profile, Mainlevel " + \
                str(mainLevel)
        elif profile == 3:
            capability = "Broadcast Contribution Multi-tile Reversible Profile, Mainlevel " + \
                str(mainLevel)
        elif profile == 4:
            capability = "2k IMF Single Tile Lossy Profile, Mainlevel " + \
                str(mainLevel) + "; Sublevel " + str(subLevel)
        elif profile == 5:
            capability = "4k IMF Single Tile Lossy Profile, Mainlevel " + \
                str(mainLevel) + "; Sublevel " + str(subLevel)
        elif profile == 6:
            capability = "8k IMF Single Tile Lossy Profile, Mainlevel " + \
                str(mainLevel) + "; Sublevel " + str(subLevel)
        elif profile == 7:
            capability = "2k IMF Single/Multi Tile Reversible Profile, Mainlevel " + \
                str(mainLevel) + "; Sublevel " + str(subLevel)
        elif profile == 8:
            capability = "4k IMF Single/Multi Tile Reversible Profile, Mainlevel " + \
                str(mainLevel) + "; Sublevel " + str(subLevel)
        elif profile == 9:
            capability = "8k IMF Single/Multi Tile Reversible Profile, Mainlevel " + \
                str(mainLevel) + "; Sublevel " + str(subLevel)
        elif profile == 15 and subLevel == 15 and mainLevel == 15:
            capability = "Profile signalled in Profile Marker"
        else:
            capability = "Unknown (value not defined in ISO/IEC 15444-1)"

        self.addCharacteristic("capability", capability)

        # Width of reference grid
        xsiz = bc.bytesToUInt(self.boxContents[4:8])
        self.addCharacteristic("xsiz", xsiz)

        # xsiz must be within range 1 - (2**32)-1
        self.testFor("xsizIsValid", 1 <= xsiz <= (2 ** 32) - 1)

        # Height of reference grid
        ysiz = bc.bytesToUInt(self.boxContents[8:12])
        self.addCharacteristic("ysiz", ysiz)

        # ysiz must be within range 1 - (2**32)-1
        self.testFor("ysizIsValid", 1 <= ysiz <= (2 ** 32) - 1)

        # Horizontal offset from origin of reference grid to left of image area
        xOsiz = bc.bytesToUInt(self.boxContents[12:16])
        self.addCharacteristic("xOsiz", xOsiz)

        # xOsiz must be within range 0 - (2**32)-2
        self.testFor("xOsizIsValid", 0 <= xOsiz <= (2 ** 32) - 2)

        # Vertical offset from origin of reference grid to top of image area
        yOsiz = bc.bytesToUInt(self.boxContents[16:20])
        self.addCharacteristic("yOsiz", yOsiz)

        # yOsiz must be within range 0 - (2**32)-2
        self.testFor("yOsizIsValid", 0 <= yOsiz <= (2 ** 32) - 2)

        # Width of one reference tile with respect to the reference grid
        xTsiz = bc.bytesToUInt(self.boxContents[20:24])
        self.addCharacteristic("xTsiz", xTsiz)

        # xTsiz must be within range 1 - (2**32)- 1
        self.testFor("xTsizIsValid", 1 <= xTsiz <= (2 ** 32) - 1)

        # Height of one reference tile with respect to the reference grid
        yTsiz = bc.bytesToUInt(self.boxContents[24:28])
        self.addCharacteristic("yTsiz", yTsiz)

        # yTsiz must be within range 1 - (2**32)- 1
        self.testFor("yTsizIsValid", 1 <= yTsiz <= (2 ** 32) - 1)

        # Horizontal offset from origin of reference grid to left side of first
        # tile
        xTOsiz = bc.bytesToUInt(self.boxContents[28:32])
        self.addCharacteristic("xTOsiz", xTOsiz)

        # xTOsiz must be within range 0 - (2**32)-2
        self.testFor("xTOsizIsValid", 0 <= xTOsiz <= (2 ** 32) - 2)

        # Vertical offset from origin of reference grid to top side of first
        # tile
        yTOsiz = bc.bytesToUInt(self.boxContents[32:36])
        self.addCharacteristic("yTOsiz", yTOsiz)

        # yTOsiz must be within range 0 - (2**32)-2
        self.testFor("yTOsizIsValid", 0 <= yTOsiz <= (2 ** 32) - 2)

        # Relations between the fields (Section A.5.1): the image area is not
        # empty, the tile grid starts at or before the image area, and the
        # first tile overlaps the image area
        self.testFor("imageAreaIsValid", xOsiz < xsiz and yOsiz < ysiz)
        self.testFor("tileOffsetIsValid", xTOsiz <= xOsiz and yTOsiz <= yOsiz)
        self.testFor("firstTileOverlapsImageArea",
                     xTsiz + xTOsiz > xOsiz and yTsiz + yTOsiz > yOsiz)

        # Number of tiles
        if xTsiz != 0 and yTsiz != 0:
            # If block to prevent zero-division (which should not happen
            # for valid files)
            # Clamp at 0: with a tile offset beyond the image both factors are
            # negative, and their product would be a positive tile count
            numberOfTilesX = max(math.ceil((xsiz - xTOsiz) / xTsiz), 0)
            numberOfTilesY = max(math.ceil((ysiz - yTOsiz) / yTsiz), 0)
            numberOfTiles = int(numberOfTilesX * numberOfTilesY)
        else:
            # Bogus value
            numberOfTiles = 0

        self.addCharacteristic("numberOfTiles", numberOfTiles)

        # Number of components
        csiz = bc.bytesToUShortInt(self.boxContents[36:38])
        self.addCharacteristic("csiz", csiz)

        # Number of components must be in range 1 - 16384 (including limits)
        self.testFor("csizIsValid", 1 <= csiz <= 16384)

        # Check if codestream header size is consistent with csiz
        self.testFor("lsizConsistentWithCsiz", lsiz == 38 + (3 * csiz))

        # Precision, depth horizontal/verical separation repeated for each
        # component

        offset = 38

        for _ in range(csiz):
            # ssiz (=bits per component)
            ssiz = bc.bytesToUnsignedChar(self.boxContents[offset:offset + 1])

            # Most significant bit indicates whether components are signed (1)
            # or unsigned (0). Extracted by applying bit mask of 10000000
            # (=128)
            ssizSign = bc.getBitValue(ssiz, 1)
            self.addCharacteristic("ssizSign", ssizSign)

            # Remaining bits indicate (bit depth - 1). Extracted by applying bit mask of
            # 01111111 (=127)
            ssizDepth = (ssiz & 127) + 1
            self.addCharacteristic("ssizDepth", ssizDepth)

            # ssiz field is valid if ssizDepth in range 1-38
            self.testFor("ssizIsValid", 1 <= ssizDepth <= 38)

            # Horizontal separation of sample of this component with respect
            # to reference grid
            xRsiz = bc.bytesToUnsignedChar(
                self.boxContents[offset + 1:offset + 2])
            self.addCharacteristic("xRsiz", xRsiz)

            # xRSiz valid if range 1-255
            self.testFor("xRsizIsValid", 1 <= xRsiz <= 255)

            # Vertical separation of sample of this component with respect
            # to reference grid
            yRsiz = bc.bytesToUnsignedChar(
                self.boxContents[offset + 2:offset + 3])
            self.addCharacteristic("yRsiz", yRsiz)

            # yRSiz valid if range 1-255
            self.testFor("yRsizIsValid", 1 <= yRsiz <= 255)

            offset += 3

    def validate_cod(self):
        """Coding style default (COD) header fields (ISO/IEC 15444-1 Section A.6.1);
        ISO/IEC 15444-15 Section A.4)."""
        # Length of COD marker
        lcod = bc.bytesToUShortInt(self.boxContents[0:2])
        self.addCharacteristic("lcod", lcod)

        # lcod must be in range 12-45
        lcodIsValid = 12 <= lcod <= 45
        self.testFor("lcodIsValid", lcodIsValid)

        # Coding style
        scod = bc.bytesToUnsignedChar(self.boxContents[2:3])

        # scod contains 3 coding style parameters that follow from its 3 least
        # significant bits

        # Last bit: 0 in case of default precincts (ppx/ppy=15), 1 in case precincts
        # are defined in sPcod parameter
        precincts = bc.getBitValue(scod, 8)
        self.addCharacteristic("precincts", precincts)

        # 7th bit: 0: no start of packet marker segments; 1: start of packet marker
        # segments may be used
        sop = bc.getBitValue(scod, 7)
        self.addCharacteristic("sop", sop)

        # 6th bit: 0: no end of packet marker segments; 1: end of packet marker
        # segments shall be used
        eph = bc.getBitValue(scod, 6)
        self.addCharacteristic("eph", eph)

        # Coding parameters that are independent of components (grouped as sGCod)
        # in standard)

        sGcod = self.boxContents[3:7]

        # Progression order
        order = bc.bytesToUnsignedChar(sGcod[0:1])
        self.addCharacteristic("order", order)

        # Allowed values: 0 (LRCP), 1 (RLCP), 2 (RPCL), 3 (PCRL), 4(CPRL)
        orderIsValid = order in [0, 1, 2, 3, 4]
        self.testFor("orderIsValid", orderIsValid)

        # Number of layers
        layers = bc.bytesToUShortInt(sGcod[1:3])
        self.addCharacteristic("layers", layers)

        # layers must be in range 1-65535
        layersIsValid = 1 <= layers <= 65535
        self.testFor("layersIsValid", layersIsValid)

        # Multiple component transformation
        multipleComponentTransformation = bc.bytesToUnsignedChar(sGcod[3:4])
        self.addCharacteristic(
            "multipleComponentTransformation", multipleComponentTransformation)

        # Value must be 0 (no transformation) or 1 (transformation on components
        # 0,1 and 2)
        multipleComponentTransformationIsValid = multipleComponentTransformation in [
            0, 1]
        self.testFor("multipleComponentTransformationIsValid",
                     multipleComponentTransformationIsValid)

        # Coding parameters that are component-specific (grouped as sPCod)
        # in standard)

        # Number of decomposition levels
        levels = bc.bytesToUnsignedChar(self.boxContents[7:8])
        self.addCharacteristic("levels", levels)

        # levels must be within range 0-32
        levelsIsValid = 0 <= levels <= 32
        self.testFor("levelsIsValid", levelsIsValid)

        # Check lcod is consistent with levels and precincts (eq A-2 )

        if precincts == 1:
            lcodExpected = 13 + levels
        else:
            lcodExpected = 12

        lcodConsistencyCheck = lcod == lcodExpected
        self.testFor(
            "lcodConsistencyCheck", lcodConsistencyCheck)

        # Code block width exponent (stored as offsets, add 2 to get actual
        # value)
        codeBlockWidthExponent = bc.bytesToUnsignedChar(
            self.boxContents[8:9]) + 2
        self.addCharacteristic("codeBlockWidth",
                               self._codeBlockSize(codeBlockWidthExponent))

        # Value within range 2-10
        codeBlockWidthExponentIsValid = 2 <= codeBlockWidthExponent <= 10
        self.testFor(
            "codeBlockWidthExponentIsValid", codeBlockWidthExponentIsValid)

        # Code block height exponent (stored as offsets, add 2 to get actual
        # value)
        codeBlockHeightExponent = bc.bytesToUnsignedChar(
            self.boxContents[9:10]) + 2
        self.addCharacteristic("codeBlockHeight",
                               self._codeBlockSize(codeBlockHeightExponent))

        # Value within range 2-10
        codeBlockHeightExponentIsValid = 2 <= codeBlockHeightExponent <= 10
        self.testFor(
            "codeBlockHeightExponentIsValid", codeBlockHeightExponentIsValid)

        # Sum of width + height exponents mustn't exceed 12
        sumHeightWidthExponentIsValid = codeBlockWidthExponent + \
            codeBlockHeightExponent <= 12
        self.testFor(
            "sumHeightWidthExponentIsValid", sumHeightWidthExponentIsValid)

        # Code block style, contains several boolean switches
        codeBlockStyle = bc.bytesToUnsignedChar(self.boxContents[10:11])

        if self.format in ['jph', 'jhc']:
            # resetOnBoundaries, predTermination and segmentationSymbols are undefined
            # for HT blocks. Below flag is True if all code blocks are HT .
            mask = 0b11000000
            # Only HT blocks if 1st bit 0, 2nd 1, resulting in decimal value 64
            onlyHT = mask & codeBlockStyle == 64
        else:
            onlyHT = False

        # Bit 8: selective arithmetic coding bypass
        codingBypass = bc.getBitValue(codeBlockStyle, 8)
        self.addCharacteristic("codingBypass", codingBypass)

        # Bit 7: reset of context probabilities on coding pass boundaries
        if not onlyHT:
            resetOnBoundaries = bc.getBitValue(codeBlockStyle, 7)
            self.addCharacteristic("resetOnBoundaries", resetOnBoundaries)

        # Bit 6: termination on each coding pass
        termOnEachPass = bc.getBitValue(codeBlockStyle, 6)
        self.addCharacteristic("termOnEachPass", termOnEachPass)

        # Bit 5: vertically causal context
        vertCausalContext = bc.getBitValue(codeBlockStyle, 5)
        self.addCharacteristic("vertCausalContext", vertCausalContext)

        # Bit 4: predictable termination
        if not onlyHT:
            predTermination = bc.getBitValue(codeBlockStyle, 4)
            self.addCharacteristic("predTermination", predTermination)

        # Bit 3: segmentation symbols are used
        if not onlyHT:
            segmentationSymbols = bc.getBitValue(codeBlockStyle, 3)
            self.addCharacteristic("segmentationSymbols", segmentationSymbols)

        # Wavelet transformation: 9-7 irreversible (0) or 5-3 reversible (1)
        transformation = bc.bytesToUnsignedChar(self.boxContents[11:12])
        self.addCharacteristic("transformation", transformation)

        transformationIsValid = transformation in [0, 1]
        self.testFor("transformationIsValid", transformationIsValid)

        if precincts == 1:

            # Precinct size for each resolution level (=decomposition levels +1)
            # Order: low to high (lowest first)

            offset = 12

            for i in range(levels + 1):
                # Precinct byte
                precinctByte = bc.bytesToUnsignedChar(
                    self.boxContents[offset:offset + 1])

                # Precinct width exponent: least significant 4 bytes (apply bit
                # mask)
                ppx = precinctByte & 15
                precinctSizeX = 2 ** ppx
                self.addCharacteristic("precinctSizeX", precinctSizeX)

                # Precinct size of 1 (exponent 0) only allowed for lowest
                # resolution level
                if i != 0:
                    precinctSizeXIsValid = precinctSizeX >= 2
                else:
                    precinctSizeXIsValid = True

                self.testFor("precinctSizeXIsValid", precinctSizeXIsValid)

                # Precinct height exponent: most significant 4 bytes (shift 4
                # to right and apply bit mask)
                ppy = (precinctByte >> 4) & 15
                precinctSizeY = 2 ** ppy
                self.addCharacteristic("precinctSizeY", precinctSizeY)

                # Precinct size of 1 (exponent 0) only allowed for lowest
                # resolution level
                if i != 0:
                    precinctSizeYIsValid = precinctSizeY >= 2
                else:
                    precinctSizeYIsValid = True

                self.testFor("precinctSizeYIsValid", precinctSizeYIsValid)
                offset += 1

        else:

            # Default size for all precincts
            for i in range(levels + 1):
                precinctSizeX = 2 ** 15
                self.addCharacteristic("precinctSizeX", precinctSizeX)
                precinctSizeY = 2 ** 15
                self.addCharacteristic("precinctSizeY", precinctSizeY)

    def validate_coc(self):
        """Coding style component (COC) header fields (ISO/IEC 15444-1 Section A.6.2);
        ISO/IEC 15444-15 Section A.4)."""
        # Length of COC marker
        lcoc = bc.bytesToUShortInt(self.boxContents[0:2])
        self.addCharacteristic("lcoc", lcoc)

        # lcod must be in range 9-43
        lcocIsValid = 9 <= lcoc <= 43
        self.testFor("lcocIsValid", lcocIsValid)

        # Size of following field and offset of fields that follow it depend on
        # csiz value
        if self.csiz < 257:
            # Index of component to which this marker relates
            ccoc = bc.bytesToUnsignedChar(self.boxContents[2:3])
            offset = 3
        else:
            ccoc = bc.bytesToUShortInt(self.boxContents[2:4])
            offset = 4

        self.addCharacteristic("ccoc", ccoc)
        # Must refer to an existing component
        self.testFor("ccocIsValid", 0 <= ccoc < self.csiz)

        # Coding style for this component
        scoc = bc.bytesToUnsignedChar(self.boxContents[offset:offset + 1])
        # Last bit of scoc: 0 in case of default precincts (ppx/ppy=15), 1 in case precincts
        # are defined in sPcoc parameter
        precincts = bc.getBitValue(scoc, 8)
        self.addCharacteristic("precincts", precincts)
        offset += 1

        # Coding parameters that are component-specific (grouped as sPCoc)
        # in standard)

        # Number of decomposition levels
        levels = bc.bytesToUnsignedChar(self.boxContents[offset:offset + 1])
        self.addCharacteristic("levels", levels)

        # levels must be within range 0-32
        levelsIsValid = 0 <= levels <= 32
        self.testFor("levelsIsValid", levelsIsValid)

        # Check lcoc is consistent with levels and precincts (eq A-3)
        if precincts == 1 and self.csiz < 257:
            lcocExpected = 10 + levels
        elif precincts == 1 and self.csiz >= 257:
            lcocExpected = 11 + levels
        elif precincts == 0 and self.csiz < 257:
            lcocExpected = 9
        else:
            lcocExpected = 10

        lcocConsistencyCheck = lcoc == lcocExpected
        self.testFor(
            "lcocConsistencyCheck", lcocConsistencyCheck)

        offset += 1

        # Code block width exponent (stored as offsets, add 2 to get actual
        # value)
        codeBlockWidthExponent = bc.bytesToUnsignedChar(
            self.boxContents[offset:offset + 1]) + 2
        self.addCharacteristic("codeBlockWidth",
                               self._codeBlockSize(codeBlockWidthExponent))

        # Value within range 2-10
        codeBlockWidthExponentIsValid = 2 <= codeBlockWidthExponent <= 10
        self.testFor(
            "codeBlockWidthExponentIsValid", codeBlockWidthExponentIsValid)

        offset += 1

        # Code block height exponent (stored as offsets, add 2 to get actual
        # value)
        codeBlockHeightExponent = bc.bytesToUnsignedChar(
            self.boxContents[offset:offset + 1]) + 2
        self.addCharacteristic("codeBlockHeight",
                               self._codeBlockSize(codeBlockHeightExponent))

        # Value within range 2-10
        codeBlockHeightExponentIsValid = 2 <= codeBlockHeightExponent <= 10
        self.testFor(
            "codeBlockHeightExponentIsValid", codeBlockHeightExponentIsValid)

        # Sum of width + height exponents mustn't exceed 12
        sumHeightWidthExponentIsValid = codeBlockWidthExponent + \
            codeBlockHeightExponent <= 12
        self.testFor(
            "sumHeightWidthExponentIsValid", sumHeightWidthExponentIsValid)

        offset += 1

        # Code block style, contains several boolean switches
        codeBlockStyle = bc.bytesToUnsignedChar(
            self.boxContents[offset:offset + 1])

        if self.format in ['jph', 'jhc']:
            # resetOnBoundaries, predTermination and segmentationSymbols are undefined
            # for HT blocks. Below flag is True if all code blocks are HT .
            mask = 0b11000000
            # Only HT blocks if 1st bit 0, 2nd 1, resulting in decimal value 64
            onlyHT = mask & codeBlockStyle == 64
        else:
            onlyHT = False

        # Bit 8: selective arithmetic coding bypass
        codingBypass = bc.getBitValue(codeBlockStyle, 8)
        self.addCharacteristic("codingBypass", codingBypass)

        # Bit 7: reset of context probabilities on coding pass boundaries
        if not onlyHT:
            resetOnBoundaries = bc.getBitValue(codeBlockStyle, 7)
            self.addCharacteristic("resetOnBoundaries", resetOnBoundaries)

        # Bit 6: termination on each coding pass
        termOnEachPass = bc.getBitValue(codeBlockStyle, 6)
        self.addCharacteristic("termOnEachPass", termOnEachPass)

        # Bit 5: vertically causal context
        vertCausalContext = bc.getBitValue(codeBlockStyle, 5)
        self.addCharacteristic("vertCausalContext", vertCausalContext)

        # Bit 4: predictable termination
        if not onlyHT:
            predTermination = bc.getBitValue(codeBlockStyle, 4)
            self.addCharacteristic("predTermination", predTermination)

        # Bit 3: segmentation symbols are used
        if not onlyHT:
            segmentationSymbols = bc.getBitValue(codeBlockStyle, 3)
            self.addCharacteristic("segmentationSymbols", segmentationSymbols)

        offset += 1

        # Wavelet transformation: 9-7 irreversible (0) or 5-3 reversible (1)
        transformation = bc.bytesToUnsignedChar(
            self.boxContents[offset:offset + 1])
        self.addCharacteristic("transformation", transformation)

        transformationIsValid = transformation in [0, 1]
        self.testFor("transformationIsValid", transformationIsValid)

        if precincts == 1:

            # Precinct size for each resolution level (= decomposition levels + 1)
            # Order: low to high (lowest first)
            # TODO: the behaviour in the case of precincts is untested at this stage
            # due to a lack of test files!

            offset += 1

            for i in range(levels + 1):
                # Precinct byte
                precinctByte = bc.bytesToUnsignedChar(
                    self.boxContents[offset:offset + 1])

                # Precinct width exponent: least significant 4 bytes (apply bit
                # mask)
                ppx = precinctByte & 15
                precinctSizeX = 2 ** ppx
                self.addCharacteristic("precinctSizeX", precinctSizeX)

                # Precinct size of 1 (exponent 0) only allowed for lowest
                # resolution level
                if i != 0:
                    precinctSizeXIsValid = precinctSizeX >= 2
                else:
                    precinctSizeXIsValid = True

                self.testFor("precinctSizeXIsValid", precinctSizeXIsValid)

                # Precinct height exponent: most significant 4 bytes (shift 4
                # to right and apply bit mask)
                ppy = (precinctByte >> 4) & 15
                precinctSizeY = 2 ** ppy
                self.addCharacteristic("precinctSizeY", precinctSizeY)

                # Precinct size of 1 (exponent 0) only allowed for lowest
                # resolution level
                if i != 0:
                    precinctSizeYIsValid = precinctSizeY >= 2
                else:
                    precinctSizeYIsValid = True

                self.testFor("precinctSizeYIsValid", precinctSizeYIsValid)
                offset += 1

        else:

            # Default size for all precincts
            for i in range(levels + 1):
                precinctSizeX = 2 ** 15
                self.addCharacteristic("precinctSizeX", precinctSizeX)
                precinctSizeY = 2 ** 15
                self.addCharacteristic("precinctSizeY", precinctSizeY)

    def validate_rgn(self):
        """Region of interest (RGN) header fields (ISO/IEC 15444-1 Section A.6.3;
        ISO/IEC 15444-15 Section A.5)."""
        # Length of RGN marker
        lrgn = bc.bytesToUShortInt(self.boxContents[0:2])
        self.addCharacteristic("lrgn", lrgn)

        # lrgn must be 5 (csiz < 257) or 6 (2-byte component index)
        lrgnIsValid = lrgn == (5 if self.csiz < 257 else 6)
        self.testFor("lrgnIsValid", lrgnIsValid)

        # Size of following field and offset of fields that follow it depend on
        # csiz value
        if self.csiz < 257:
            # Index of component to which this marker relates
            crgn = bc.bytesToUnsignedChar(self.boxContents[2:3])
            offset = 3
        else:
            crgn = bc.bytesToUShortInt(self.boxContents[2:4])
            offset = 4

        self.addCharacteristic("crgn", crgn)
        # Must refer to an existing component
        self.testFor("crgnIsValid", 0 <= crgn < self.csiz)

        # ROI style for the current ROI
        roiStyle = bc.bytesToUnsignedChar(self.boxContents[offset:offset + 1])
        self.addCharacteristic("roiStyle", roiStyle)

        roiStyleIsValid = roiStyle == 0
        self.testFor("roiStyleIsValid", roiStyleIsValid)

        offset += 1

        # Implicit ROI shift
        roiShift = bc.bytesToUnsignedChar(self.boxContents[offset:offset + 1])
        self.addCharacteristic("roiShift", roiShift)

        if self.format in ['jph', 'jhc']:
            roiShiftIsValid = 0 <= roiShift <= 37
        else:
            roiShiftIsValid = 0 <= roiShift <= 255

        self.testFor("roiShiftIsValid", roiShiftIsValid)

    def _addQuantizationValues(self, qStyle, length, offset, testName):
        """Report the SPqcd/SPqcc values of a QCD/QCC marker segment, which start
        at offset, and test that the segment length matches the quantization
        style (ISO/IEC 15444-1 Eq A-4, A-5).

        Styles 0 and 2 have one value per subband: 3 * (number of decomposition
        levels) + 1, in codestream order (NL LL, then HL, LH, HH from level NL
        down to 1). Style 1 has a single value.
        """
        noValueBytes = length - offset
        # Don't read beyond a truncated segment
        available = min(length, len(self.boxContents)) - offset

        if qStyle == 0:
            # One byte per subband: 5 most significant bits -> exponent epsilon in Eq E-5
            for spq in self.boxContents[offset:offset + available]:
                self.addCharacteristic("epsilon", (spq >> 3) & 31)
            self.testFor(testName, noValueBytes >= 1 and (noValueBytes - 1) % 3 == 0)

        elif qStyle in [1, 2]:
            # Two bytes per value: 11 least significant bits -> mu, 5 most
            # significant bits -> exponent epsilon in Eq E-3
            noValues = max(available, 0) // 2
            if qStyle == 1:
                noValues = min(noValues, 1)
            for i in range(noValues):
                spq = bc.bytesToUShortInt(
                    self.boxContents[offset + 2 * i:offset + 2 * i + 2])
                self.addCharacteristic("mu", spq & 2047)
                self.addCharacteristic("epsilon", (spq >> 11) & 31)

            if qStyle == 1:
                self.testFor(testName, noValueBytes == 2)
            else:
                self.testFor(testName, noValueBytes >= 2 and noValueBytes % 2 == 0 and
                             (noValueBytes // 2 - 1) % 3 == 0)

    def validate_qcd(self):
        """Quantization default (QCD) header fields (ISO/IEC 15444-1 Section A.6.4)."""
        # Length of QCD marker
        lqcd = bc.bytesToUShortInt(self.boxContents[0:2])
        self.addCharacteristic("lqcd", lqcd)

        # lqcd must be in range 4-197
        lqcdIsValid = 4 <= lqcd <= 197
        self.testFor("lqcdIsValid", lqcdIsValid)

        # Quantization style for all components
        sqcd = bc.bytesToUnsignedChar(self.boxContents[2:3])

        # sqcd contains 2 quantization parameters: style + no of guard bits

        # Style: least significant 5 bytes (apply bit mask)
        qStyle = sqcd & 31
        self.addCharacteristic("qStyle", qStyle)

        # Allowed values: 0 (no quantization), 1 (scalar derived), 2 (scalar
        # expounded)
        qStyleIsValid = qStyle in [0, 1, 2]
        self.testFor("qStyleIsValid", qStyleIsValid)

        # Number of guard bits (3 most significant bits, shift + bit mask)
        guardBits = (sqcd >> 5) & 7
        self.addCharacteristic("guardBits", guardBits)

        # Quantization values for each subband
        self._addQuantizationValues(qStyle, lqcd, 3, "lqcdConsistentWithQStyle")

    def validate_qcc(self):
        """Quantization component (QCC) header fields (ISO/IEC 15444-1 Section A.6.5)."""
        # Length of QCC marker
        lqcc = bc.bytesToUShortInt(self.boxContents[0:2])
        self.addCharacteristic("lqcc", lqcc)

        # lqcc must be in range 5-199
        lqccIsValid = 5 <= lqcc <= 199
        self.testFor("lqccIsValid", lqccIsValid)

        # Size of following field and offset of fields that follow it depend on
        # csiz value
        if self.csiz < 257:
            # Index of component to which this marker relates
            cqcc = bc.bytesToUnsignedChar(self.boxContents[2:3])
            offset = 3
        else:
            cqcc = bc.bytesToUShortInt(self.boxContents[2:4])
            offset = 4

        self.addCharacteristic("cqcc", cqcc)
        # Must refer to an existing component
        self.testFor("cqccIsValid", 0 <= cqcc < self.csiz)

        # Quantization style for this component
        sqcc = bc.bytesToUnsignedChar(self.boxContents[offset:offset + 1])

        # sqcc contains 2 quantization parameters: style + no of guard bits

        # Style: least significant 5 bytes (apply bit mask)
        qStyle = sqcc & 31
        self.addCharacteristic("qStyle", qStyle)

        # Allowed values: 0 (no quantization), 1 (scalar derived), 2 (scalar
        # expounded)
        qStyleIsValid = qStyle in [0, 1, 2]
        self.testFor("qStyleIsValid", qStyleIsValid)

        # Number of guard bits (3 most significant bits, shift + bit mask)
        guardBits = (sqcc >> 5) & 7
        self.addCharacteristic("guardBits", guardBits)

        # Quantization values for each subband
        self._addQuantizationValues(qStyle, lqcc, offset + 1, "lqccConsistentWithQStyle")

    def validate_poc(self):
        """Progression order change (POC) header fields (ISO/IEC 15444-1 Section A.6.6)."""
        # Length of POC marker
        lpoc = bc.bytesToUShortInt(self.boxContents[0:2])
        self.addCharacteristic("lpoc", lpoc)

        # lpoc must be 2 plus a whole, non-zero number of progression order
        # changes of 7 bytes (csiz < 257) or 9 bytes each (Eq A-6)
        changeSize = 7 if self.csiz < 257 else 9
        lpocIsValid = 2 + changeSize <= lpoc <= 65535 and (lpoc - 2) % changeSize == 0
        self.testFor("lpocIsValid", lpocIsValid)

        # Get number of progression order changes from re-arranged form of Eq
        # A-6
        if self.csiz < 257:
            progOrderChanges = int((lpoc - 2) / 7)
        else:
            progOrderChanges = int((lpoc - 2) / 9)

        offset = 2

        for _ in range(progOrderChanges):
            # Resolution index for the start of a progression
            rspoc = bc.bytesToUnsignedChar(self.boxContents[offset:offset + 1])
            self.addCharacteristic("rspoc", rspoc)

            # rspoc must be within range 0-32
            rspocIsValid = 0 <= rspoc <= 32
            self.testFor("rspocIsValid", rspocIsValid)

            offset += 1

            # Component index for start of progression. Has 1 or 2 bytes size, depending
            # on csiz
            if self.csiz < 257:
                cspoc = bc.bytesToUnsignedChar(
                    self.boxContents[offset:offset + 1])
                cspocIsValid = 0 <= cspoc <= 255
                offset += 1
            else:
                cspoc = bc.bytesToUShortInt(
                    self.boxContents[offset:offset + 2])
                cspocIsValid = 0 <= cspoc <= 16383
                offset += 2

            self.addCharacteristic("cspoc", cspoc)
            self.testFor("cspocIsValid", cspocIsValid)

            # Layer index for end of progression
            lyepoc = bc.bytesToUShortInt(self.boxContents[offset:offset + 2])
            self.addCharacteristic("lyepoc", lyepoc)
            lyepocIsValid = 1 <= lyepoc <= 65535
            self.testFor("lyepocIsValid", lyepocIsValid)
            offset += 2

            # Resolution level index for end of progression
            repoc = bc.bytesToUnsignedChar(self.boxContents[offset:offset + 1])
            self.addCharacteristic("repoc", repoc)
            repocIsValid = (rspoc + 1) <= repoc <= 33
            self.testFor("repocIsValid", repocIsValid)
            offset += 1

            # Component index for end of progression. Has 1 or 2 bytes size, depending
            # on csiz
            if self.csiz < 257:
                cepoc = bc.bytesToUnsignedChar(
                    self.boxContents[offset:offset + 1])
                cepocIsValid = (cspoc + 1) <= cepoc <= 255 or cepoc == 0
                offset += 1
            else:
                cepoc = bc.bytesToUShortInt(
                    self.boxContents[offset:offset + 2])
                cepocIsValid = (cspoc + 1) <= cepoc <= 16384 or cepoc == 0
                offset += 2

            self.addCharacteristic("cepoc", cepoc)
            self.testFor("cepocIsValid", cepocIsValid)

            # Progression order
            order = bc.bytesToUnsignedChar(self.boxContents[offset:offset + 1])
            self.addCharacteristic("order", order)

            # Allowed values: 0 (LRCP), 1 (RLCP), 2 (RPCL), 3 (PCRL), 4(CPRL)
            orderIsValid = order in [0, 1, 2, 3, 4]
            self.testFor("orderIsValid", orderIsValid)
            offset += 1

    def validate_crg(self):
        """Component registration (CRG) marker (ISO/IEC 15444-1 Section A.9.1)."""
        # Length of CRGM marker
        lcrg = bc.bytesToUShortInt(self.boxContents[0:2])
        self.addCharacteristic("lcrg", lcrg)

        # lcrg must equal 2 + 4 * csiz (one Xcrg, Ycrg pair per component)
        lcrgIsValid = lcrg == 2 + 4 * self.csiz
        self.testFor("lcrgIsValid", lcrgIsValid)

        offset = 2

        for _ in range(self.csiz):
            # Horizontal offset value, in units of 1/65535 of xRsiz
            xcrg = bc.bytesToUShortInt(self.boxContents[offset:offset + 2])
            self.addCharacteristic("xcrg", xcrg)
            xcrgIsValid = 0 <= xcrg <= 65535
            self.testFor("xcrgIsValid", xcrgIsValid)
            offset += 2
            # Vertical offset value, in units of 1/65535 of yRsiz
            ycrg = bc.bytesToUShortInt(self.boxContents[offset:offset + 2])
            self.addCharacteristic("ycrg", ycrg)
            ycrgIsValid = 0 <= ycrg <= 65535
            self.testFor("ycrgIsValid", ycrgIsValid)
            offset += 2

    def validate_com(self):
        """Codestream comment (COM) (ISO/IEC 15444-1 Section A.9.2)."""
        # Length of COM marker
        lcom = bc.bytesToUShortInt(self.boxContents[0:2])
        self.addCharacteristic("lcom", lcom)

        # lcom must be in range 5-65535
        lcomIsValid = 5 <= lcom <= 65535
        self.testFor("lcomIsValid", lcomIsValid)

        # Registration value of marker segment
        rcom = bc.bytesToUShortInt(self.boxContents[2:4])
        self.addCharacteristic("rcom", rcom)

        # rcom must be either 0 (binary values) or 1 (ISO/IEC 8859-15 (Latin)
        # values)
        rcomIsValid = 0 <= rcom <= 1
        self.testFor("rcomIsValid", rcomIsValid)

        # Contents (multiples of Ccom)
        comment = self.boxContents[4:lcom]

        if rcom == 0:
            # no validation of binary comment content
            commentIsValid = True
            comment = bc.bytesToHex(comment)

        elif rcom == 1:

            # Decode to string with Latin encoding, determine if valid ISO
            # 8859-15

            try:
                comment = comment.decode("iso-8859-15", "strict")
            except UnicodeError:
                # Empty string in case of decode error
                comment = ""

            # Ideally decode above should raise exception if comment is not
            # valid ISO 8859-15, but this doesn't work. So instead we do this
            # indirectly by looking for control characters (tab, newline and
            # carriage return are OK)
            commentIsValid = bool(bc.removeControlCharacters(comment) == comment)

        else:

            # Value of rcom value that is nor defined by the standard
            commentIsValid = False

        self.testFor("commentIsValid", commentIsValid)

        # any non-printable data should have been removed.
        if commentIsValid:
            self.addCharacteristic("comment", comment)

    def validate_cap(self):
        """Extended capabilities marker (CAP) marker segment (15444-1, Section A.5.2)."""

        # Length of CAP marker
        lcap = bc.bytesToUShortInt(self.boxContents[0:2])
        self.addCharacteristic("lcap", lcap)

        # Pcap
        pcap = bc.bytesToUInt(self.boxContents[2:6])

        # Extract values of individual bits in pcap to list (none if pcap
        # could not be read)
        numBits = 32
        pcapBits = [(pcap >> bit) & 1 for bit in range(numBits - 1, -1, -1)] \
            if pcap != -9999 else []

        # List of all referenced ISO parts.
        pcapParts = []

        # Populate list. Index i of each non-zero bit corresponds to capabilities
        # defined by part i+1 of ISO/IEC 15444
        for i, bit in enumerate(pcapBits):
            if bit == 1:
                pcapPart = i + 1
                pcapParts.append(pcapPart)
                # Report referenced ISO/IEC 15444 part
                self.addCharacteristic("pcapPart", pcapPart)

        noccaps = len(pcapParts)

        # Test if noccaps is consistent with lcap
        self.testFor("lcapIsValid", pcap != -9999 and noccaps == (lcap - 6) / 2)

        # Iterate over all ccap values and put them in a list
        ccaps = []

        offset = 6

        for _ in range(noccaps):
            ccap = bc.bytesToUShortInt(self.boxContents[offset:offset + 2])
            ccaps.append(ccap)
            offset += 2

        # Meaning of ccap fields is defined in referenced parts of the standard, so
        # only process those that are known / in scope for Jpylyzer

        if self.format in ['jph', 'jhc']:
            pcap15IsValid = 15 in pcapParts
            self.testFor("pcap15IsValid", pcap15IsValid)

            if pcap15IsValid:
                ccapIndex = pcapParts.index(15)
                ccap = ccaps[ccapIndex]
                # Reported capabilities correspond to Constrained codestream sets
                # that are defined in ISO/IEC 15444-15 Sections 8.2 - 8.8

                # First field is defined by 2 most significant bits, use bit mask
                # for convenience
                mask = 0b1100000000000000
                htCodeBlocks = mask & ccap
                self.addCharacteristic("htCodeBlocks", htCodeBlocks)

                # Following fields are each 1 bit only
                htSets = bc.getBitValue(ccap, 3, wordLength=16)
                self.addCharacteristic("htSets", htSets)
                htRegion = bc.getBitValue(ccap, 4, wordLength=16)
                self.addCharacteristic("htRegion", htRegion)
                htHomogeneous = bc.getBitValue(ccap, 5, wordLength=16)
                self.addCharacteristic("htHomogeneous", htHomogeneous)
                htReversible = bc.getBitValue(ccap, 11, wordLength=16)
                self.addCharacteristic("htReversible", htReversible)

                # Final 5 bits define parameter B from MAGBP set (apply bit
                # mask)
                p = ccap & 31

                # Value of b as a function of p
                if p == 0:
                    htB = 8
                elif p < 20:
                    htB = p + 8
                elif 20 <= p < 31:
                    htB = 4 * (p - 19) + 27
                else:
                    htB = 74

                self.addCharacteristic("htB", htB)

    def validate_prf(self):
        """Profile (PRF) marker segment (15444-1, Section A.5.3)."""

        # Length of PRF marker
        lprf = bc.bytesToUShortInt(self.boxContents[0:2])
        self.addCharacteristic("lprf", lprf)

        # lprf  must be within range 4-65534
        self.testFor("lprfIsValid", 4 <= lprf <= 65534)

        # Pprf values, as far as they are present in the segment
        pprfs = self._profileWords(lprf)

        # Profile number
        PRFnum = 4095 + sum(pprf << (16 * i) for i, pprf in enumerate(pprfs))

        if pprfs:
            # last pprf shall not be zero
            self.testFor("pprfIsValid", pprfs[-1] != 0)

        self.testFor("PRFnumIsValid", PRFnum > 4095)
        self.addCharacteristic("PRFnum", self._reportableProfileNumber("PRFnum", PRFnum))

    def validate_cpf(self):
        """Corresponding profile (CPF) marker segment (15444-15, Section A.6)."""

        # Length of CPF marker
        lcpf = bc.bytesToUShortInt(self.boxContents[0:2])
        self.addCharacteristic("lcpf", lcpf)

        # lcpf  must be within range 4-65534
        if self.format in ['jph', 'jhc']:
            self.testFor("lcpfIsValid", 4 <= lcpf <= 65534)

        # Pcpf values, as far as they are present in the segment
        pcpfs = self._profileWords(lcpf)

        # Profile number
        CPFnum = -1 + sum(pcpf << (16 * i) for i, pcpf in enumerate(pcpfs))

        if pcpfs and self.format in ['jph', 'jhc']:
            # last pcpf shall not be zero
            self.testFor("pcpfIsValid", pcpfs[-1] != 0)

        self.addCharacteristic("CPFnum", self._reportableProfileNumber("CPFnum", CPFnum))

    def _profileWords(self, length):
        """16-bit Pprf/Pcpf words of a PRF or CPF segment with length field
        length, leaving out any that the segment declares but does not contain."""
        end = min(length, len(self.boxContents))
        return [bc.bytesToUShortInt(self.boxContents[offset:offset + 2])
                for offset in range(2, end - 1, 2)]

    def _reportableProfileNumber(self, name, number):
        """Profile number, or -9999 with a warning if it exceeds the 64-bit
        range that XML Schema processors accept for xs:integer (a segment can
        hold up to 32766 words, which no profile needs)."""
        if number > MAX_REPORTED_INTEGER:
            self.addWarning(name + " too large to report (more than 64 bits)")
            return -9999
        return number

    def validate_sot(self):
        """Start of tile-part (SOT) marker segment (ISO/IEC 15444-1 Section A.4.2)."""
        # Note that this validation function sets the value
        # of psot (total tile-part length) as tilePartLength!

        # Length of SOT marker
        lsot = bc.bytesToUShortInt(self.boxContents[0:2])
        self.addCharacteristic("lsot", lsot)

        # lsot must be 10
        lsotIsValid = lsot == 10
        self.testFor("lsotIsValid", lsotIsValid)

        # Tile index
        isot = bc.bytesToUShortInt(self.boxContents[2:4])
        self.addCharacteristic("isot", isot)

        # Tile index must be in range 0-65534
        isotIsValid = 0 <= isot <= 65534
        self.testFor("isotIsValid", isotIsValid)

        # Length of tile part (including this SOT)
        psot = bc.bytesToUInt(self.boxContents[4:8])
        self.addCharacteristic("psot", psot)

        # psot equals 0 (for last tile part) or greater than 14 (so range 1-13
        # is illegal)
        psotIsValid = not 1 <= psot <= 13
        self.testFor("psotIsValid", psotIsValid)

        # Tile part index
        tpsot = bc.bytesToUnsignedChar(self.boxContents[8:9])
        self.addCharacteristic("tpsot", tpsot)

        # Should be in range 0-254
        tpsotIsValid = 0 <= tpsot <= 254
        self.testFor("tpsotIsValid", tpsotIsValid)

        # Number of tile-parts of a tile in the codestream
        # Value of 0 indicates that number of tile-parts of tile in the codestream
        # is not defined in this header; otherwise value in range 1-255
        tnsot = bc.bytesToUnsignedChar(self.boxContents[9:10])
        self.addCharacteristic("tnsot", tnsot)
        self.tilePartLength = psot

    def validate_tlm(self):
        """Tile-part lengths, main header (TLM) marker segment (ISO/IEC 15444-1 Section A.7.1).
        """

        # Length of TLM marker
        ltlm = bc.bytesToUShortInt(self.boxContents[0:2])
        self.addCharacteristic("ltlm", ltlm)

        # TLM marker segment index
        ztlm = bc.bytesToUnsignedChar(self.boxContents[2:3])
        self.addCharacteristic("ztlm", ztlm)

        # Size of Ttlm and Ptlm
        stlm = bc.bytesToUnsignedChar(self.boxContents[3:4])
        st = (stlm >> 4) & 3
        self.addCharacteristic("st", st)
        self.testFor("tlmStIsValid", (st in [0, 1, 2]))

        sp = (stlm >> 6) & 1
        self.addCharacteristic("sp", sp)
        self.testFor("tlmSpIsValid", (sp in [0, 1]))

        ttlmLength = st
        ptlmLength = (sp + 1) * 2

        # Calculate number of tile parts from ltlm, st and sp, following Eq A-7:
        # each tile-part takes st bytes of Ttlm and (sp + 1) * 2 bytes of Ptlm
        if st in [0, 1, 2]:
            entrySize = ttlmLength + ptlmLength
            tpCount = int((ltlm - 4) / entrySize)
            ltlmIsValid = (ltlm - 4) % entrySize == 0
        else:
            # Bogus value in case of unexpected st values (tlmStIsValid fails)
            tpCount = 0
            ltlmIsValid = True

        self.testFor("ltlmIsValid", ltlmIsValid)
        self.addCharacteristic("tpCount", tpCount)

        if ltlmIsValid:
            offset = 4
            # iterate each tilepart Length
            for _ in range(int(tpCount)):
                if st == 1:
                    ttlm = bc.bytesToUnsignedChar(self.boxContents[offset:offset+ttlmLength])
                elif st == 2:
                    ttlm = bc.bytesToUShortInt(self.boxContents[offset:offset+ttlmLength])
                else:
                    # This covers both st = 0 (ttlm undefined) and any other illegal values
                    pass
                if st in [1, 2]:
                    self.addCharacteristic("ttlm", ttlm)
                offset += ttlmLength
                if sp == 0:
                    ptlm = bc.bytesToUShortInt(self.boxContents[offset:offset+ptlmLength])
                elif sp == 1:
                    ptlm = bc.bytesToUInt(self.boxContents[offset:offset+ptlmLength])
                else:
                    pass
                if sp in [0, 1]:
                    self.addCharacteristic("ptlm", ptlm)
                offset += ptlmLength

    # The following validator functions cover those marker segments that
    # are not yet supported, however including them has the effect that their
    # presence at least reported in jpylyzer's output.
    # Together these cover *all* the marker segments defined in ISO/IEC 15444-1,
    # apart from the SOP/EPH markers (not sure if I even *want* to see those reported
    # because there will be either lots of them or none at all!).

    def validate_plm(self):
        """Packet length, main header (PLM) marker segment (ISO/IEC 15444-1 Section A.7.2).

        The segment holds one Nplm, Iplm group per tile-part; each group is
        reported as an nplm, iplm pair.
        """
        # Length of PLM marker
        lplm = bc.bytesToUShortInt(self.boxContents[0:2])
        self.addCharacteristic("lplm", lplm)

        # PLM marker segment index
        zplm = bc.bytesToUnsignedChar(self.boxContents[2:3])
        self.addCharacteristic("zplm", zplm)

        end = min(lplm, len(self.boxContents))
        offset = 3
        while offset < end:
            # Number of bytes of Iplm information for the ith tile-part
            nplm = bc.bytesToUnsignedChar(self.boxContents[offset:offset + 1])
            self.addCharacteristic("nplm", nplm)
            groupEnd = offset + 1 + nplm
            self.testFor("nplmIsValid", groupEnd <= end)

            # Comma separated list of packet lengths
            iplm, iplmIsValid = self._parse_ipl(groupEnd, offset + 1)
            self.addCharacteristic("iplm", iplm)
            self.testFor("iplmIsValid", iplmIsValid)

            offset = groupEnd

    def validate_plt(self):
        """Packet length, tile-part header (PLT) marker segment (ISO/IEC 15444-1 Section A.7.3).

        Currently performs no validation, just adds details to properties XML.
        """
        # Length of PLT marker
        lplt = bc.bytesToUShortInt(self.boxContents[0:2])
        self.addCharacteristic("lplt", lplt)

        # PLT marker segment index
        zplt = bc.bytesToUnsignedChar(self.boxContents[2:3])
        self.addCharacteristic("zplt", zplt)

        # Comma separated list of packet lengths
        iplt, ipltIsValid = self._parse_ipl(lplt, 3)
        self.addCharacteristic("iplt", iplt)
        self.testFor("ipltIsValid", ipltIsValid)

    def validate_ppm(self):
        """Empty function."""

    def validate_ppt(self):
        """Empty function."""
