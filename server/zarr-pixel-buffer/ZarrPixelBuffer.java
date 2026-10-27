/*
 * Copyright (C) 2021 Glencoe Software, Inc. All rights reserved.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 */

package com.glencoesoftware.omero.zarr;

import com.github.benmanes.caffeine.cache.AsyncLoadingCache;
import com.github.benmanes.caffeine.cache.Caffeine;
import dev.zarr.zarrjava.core.Array;
import dev.zarr.zarrjava.core.DataType;
import java.awt.Dimension;
import java.io.IOException;
import java.nio.BufferOverflowException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutionException;
import java.util.stream.IntStream;
import java.util.stream.LongStream;
import loci.formats.FormatTools;
import ome.io.nio.DimensionsOutOfBoundsException;
import ome.io.nio.PixelBuffer;
import ome.io.nio.RomioPixelBuffer;
import ome.model.core.Pixels;
import ome.util.PixelData;
import org.slf4j.LoggerFactory;

/**
 * Subclass of ome.io.nio.PixelBuffer handling OME-Zarr data.
 **/
public class ZarrPixelBuffer implements PixelBuffer {

    private static final org.slf4j.Logger log = LoggerFactory.getLogger(ZarrPixelBuffer.class);

    /** Reference to the pixels. */
    private final Pixels pixels;

    /** Root of the OME-NGFF multiscale we are operating on. */
    private final ZarrStore root;

    /** Requested resolution level. */
    private int resolutionLevel;

    /** Total number of resolution levels. */
    private final int resolutionLevels;

    /** Max Plane Width. */
    private final Integer maxPlaneWidth;

    /** Max Plane Height. */
    private final Integer maxPlaneHeight;

    /** Zarr attributes present on the root group. */
    private final Map<String, Object> rootGroupAttributes;

    /** Zarr array corresponding to the current resolution level. */
    private Array array;

    private Map<String, Object> arrayMetadata;
    /**
     * Mapping of Z plane indexes in full resolution to Z plane indexes in current resolution.
     */
    private Map<Integer, Integer> zIndexMap;

    /** { resolutionLevel, z, c, t, x, y, w, h } vs. tile byte array cache. */
    private final AsyncLoadingCache<List<Integer>, byte[]> tileCache;

    /** Root path vs. metadata cache. */
    private final AsyncLoadingCache<ZarrPath, Map<String, Object>> zarrMetadataCache;

    /** Array path vs. ZarrArray cache. */
    private final AsyncLoadingCache<ZarrPath, Array> zarrArrayCache;

    /** Supported axes, X and Y are essential. */
    public enum Axis {
        X, Y, Z, C, T;
    }

    /** Maps axes to their corresponding indexes. */
    private Map<Axis, Integer> axesOrder;

    /**
     * Default constructor.
     *
     * @param pixels Pixels metadata for the pixel buffer
     * @param root   The root of this buffer
     */
    public ZarrPixelBuffer(Pixels pixels, ZarrStore root, Integer maxPlaneWidth,
        Integer maxPlaneHeight, AsyncLoadingCache<ZarrPath, Map<String, Object>> zarrMetadataCache,
        AsyncLoadingCache<ZarrPath, Array> zarrArrayCache) throws IOException {
        log.info("Creating ZarrPixelBuffer");
        this.pixels = pixels;
        this.root = root;
        this.zarrMetadataCache = zarrMetadataCache;
        this.zarrArrayCache = zarrArrayCache;
        try {
            Map<String, Object> tmp = this.zarrMetadataCache.get(new ZarrPath(root, "")).get();
            if (tmp.containsKey("ome")) {
                Object omeAttributes = tmp.get("ome");
                rootGroupAttributes = Utils.castToStringObjectMap(omeAttributes);
            } else {
                rootGroupAttributes = tmp;
                log.warn("Attributes should be under 'ome' key!");
            }
        } catch (ExecutionException | InterruptedException e) {
            throw new IOException(e);
        }
        if (!rootGroupAttributes.containsKey("multiscales")) {
            throw new IllegalArgumentException("Missing multiscales metadata!");
        }
        if (rootGroupAttributes.containsKey("version")) {
            log.info("NGFF version: " + rootGroupAttributes.get("version"));
        }

        getAxesOrder();
        this.resolutionLevels = this.getResolutionLevels();
        setResolutionLevel(this.resolutionLevels - 1);
        if (this.resolutionLevel < 0) {
            throw new IllegalArgumentException("This Zarr file has no pixel data");
        }

        this.maxPlaneWidth = maxPlaneWidth;
        this.maxPlaneHeight = maxPlaneHeight;

        tileCache = Caffeine.newBuilder().maximumSize(getSizeC()).buildAsync(key -> {
            int resolutionLevel = key.get(0);
            int z = key.get(1);
            int c = key.get(2);
            int t = key.get(3);
            int x = key.get(4);
            int y = key.get(5);
            int w = key.get(6);
            int h = key.get(7);
            long[] shape = new long[] { 1, 1, 1, h, w };
            byte[] innerBuffer = new byte[(int) length(shape) * getByteWidth()];
            setResolutionLevel(resolutionLevel);
            return getTileDirect(z, c, t, x, y, w, h, innerBuffer);
        });
    }

    /**
     * Get Bio-Formats/OMERO pixels type for buffer.
     *
     * @return See above.
     */
    public int getPixelsType() {
        ucar.ma2.DataType dataType = ((DataType) arrayMetadata.get("dataType")).getMA2DataType();
        switch (dataType) {
            case UBYTE:
                return FormatTools.UINT8;
            case BYTE:
                return FormatTools.INT8;
            case USHORT:
                return FormatTools.UINT16;
            case SHORT:
                return FormatTools.INT16;
            case UINT:
                return FormatTools.UINT32;
            case INT:
                return FormatTools.INT32;
            case FLOAT:
                return FormatTools.FLOAT;
            case DOUBLE:
                return FormatTools.DOUBLE;
            default:
                throw new IllegalArgumentException("Data type " + dataType + " not supported");
        }
    }

    /**
     * Calculates the pixel length of a given NumPy like "shape".
     *
     * @param shape the NumPy like "shape" to calculate the length of
     * @return See above
     * @see <a href=
     *      "https://numpy.org/doc/stable/reference/generated/numpy.shape.html">numpy.shape</a>
     *      documentation
     */
    private long length(long[] shape) {
        return LongStream.of(shape).reduce(1, Math::multiplyExact);
    }

    private void read(byte[] buffer, long[] shape, long[] offset) throws IOException {
        // Check planar read size (sizeX and sizeY only)
        checkReadSize(new long[] { shape[axesOrder.get(Axis.X)], shape[axesOrder.get(Axis.Y)] });

        // if reading from a resolution downsampled in Z,
        // adjust the shape/offset for the Z coordinate only
        // this ensures that the correct Zs are read from the correct offsets
        // since the requested shape/offset may not match the underlying array
        long originalZIndex = 1;
        if (axesOrder.containsKey(Axis.Z)) {
            originalZIndex = offset[axesOrder.get(Axis.Z)];
            if (getSizeZ() != getTrueSizeZ()) {
                offset[axesOrder.get(Axis.Z)] = zIndexMap.get(originalZIndex);
                shape[axesOrder.get(Axis.Z)] = 1;
            }
        }
        try {
            ByteBuffer asByteBuffer = ByteBuffer.wrap(buffer);
            asByteBuffer.put(array.read(offset, shape).getDataAsByteBuffer());
        } catch (Exception e) {
            log.error("Error reading Zarr data", e);
            throw new IOException(e);
        }
    }

    private PixelData toPixelData(byte[] buffer) {
        if (buffer == null) {
            return null;
        }
        PixelData d = new PixelData(FormatTools.getPixelTypeString(getPixelsType()),
            ByteBuffer.wrap(buffer));
        d.setOrder(ByteOrder.BIG_ENDIAN);
        return d;
    }

    /**
     * Retrieves the array chunk sizes of all subresolutions of this multiscale buffer.
     *
     * @return See above.
     */
    public int[][] getChunks() throws IOException {
        List<Map<String, String>> datasets = getDatasets();
        List<int[]> chunks = new ArrayList<int[]>();
        for (Map<String, String> dataset : datasets) {
            Map<String, Object> arrayMetadata = root.metadataFromArray(dataset.get("path"));
            int[] shape = (int[]) arrayMetadata.get("chunkShape");
            chunks.add(shape);
        }
        return chunks.toArray(new int[chunks.size()][]);
    }

    /**
     * Retrieves the datasets metadata of the first multiscale from the root group attributes.
     *
     * @return See above.
     * @see #getRootGroupAttributes()
     * @see #getMultiscalesMetadata()
     */
    public List<Map<String, String>> getDatasets() {
        List<Map<String, Object>> multiscales = getMultiscalesMetadata();

        Object datasets = multiscales.get(0).get("datasets");
        return Utils.castToListOfStringMap(datasets);
    }

    /**
     * Retrieves the axes order of the first multiscale.
     *
     * @return See above.
     */
    public Map<Axis, Integer> getAxesOrder() {
        if (axesOrder != null) {
            return axesOrder;
        }
        axesOrder = new HashMap<Axis, Integer>();
        List<Map<String, Object>> multiscales = getMultiscalesMetadata();
        if (multiscales.isEmpty()) {
            throw new IllegalArgumentException("No multiscales metadata found");
        }
        String version = (String) multiscales.get(0).get("version");
        Object axes = multiscales.get(0).get("axes");
        if (axes == null) {
            // The axes metadata was introduced in version 0.3 of the
            // OME-Zarr specification. Prior to this, all arrays were
            // 5 dimensional with dimensions TCZYX
            if (version != null && !version.equals("0.2") && !version.equals("0.1")) {
                throw new IllegalArgumentException("No axes metadata found");
            }
            axesOrder.put(Axis.T, 0);
            axesOrder.put(Axis.C, 1);
            axesOrder.put(Axis.Z, 2);
            axesOrder.put(Axis.Y, 3);
            axesOrder.put(Axis.X, 4);
        } else {
            List<Map<String, Object>> axesData = Utils.castToListOfObjectMap(axes);
            for (int i = 0; i < axesData.size(); i++) {
                Map<String, Object> axis = axesData.get(i);
                String name = axis.get("name").toString().toUpperCase();
                try {
                    axesOrder.put(Axis.valueOf(name), i);
                } catch (IllegalArgumentException e) {
                    throw new IllegalArgumentException(
                        "Invalid axis name (only T,C,Z,Y,X are supported): " + name);
                }
            }
        }
        if (!axesOrder.containsKey(Axis.X) || !axesOrder.containsKey(Axis.Y)) {
            throw new IllegalArgumentException("Missing X or Y axis!");
        }
        return axesOrder;
    }

    /**
     * Retrieves the multiscales metadata from the root group attributes.
     *
     * @return See above.
     * @see #getRootGroupAttributes()
     * @see #getDatasets()
     */
    public List<Map<String, Object>> getMultiscalesMetadata() {
        Object multiscales = rootGroupAttributes.get("multiscales");
        return Utils.castToListOfObjectMap(multiscales);
    }

    /**
     * Returns the current Zarr root group attributes for this buffer.
     *
     * @return See above.
     * @see #getMultiscalesMetadata()
     * @see #getDatasets()
     */
    public Map<String, Object> getRootGroupAttributes() {
        return rootGroupAttributes;
    }

    /**
     * No-op.
     */
    @Override
    public void close() throws IOException {
    }

    /**
     * Implemented as specified by {@link PixelBuffer} I/F.
     *
     * @see PixelBuffer#checkBounds(Integer, Integer, Integer, Integer, Integer)
     */
    @Override
    public void checkBounds(Integer x, Integer y, Integer z, Integer c, Integer t)
        throws DimensionsOutOfBoundsException {
        if (x != null && (x > getSizeX() - 1 || x < 0)) {
            throw new DimensionsOutOfBoundsException(
                "X '" + x + "' greater than sizeX '" + getSizeX() + "' or < '0'.");
        }
        if (y != null && (y > getSizeY() - 1 || y < 0)) {
            throw new DimensionsOutOfBoundsException(
                "Y '" + y + "' greater than sizeY '" + getSizeY() + "' or < '0'.");
        }

        if (z != null && (z > getSizeZ() - 1 || z < 0)) {
            throw new DimensionsOutOfBoundsException(
                "Z '" + z + "' greater than sizeZ '" + getSizeZ() + "' or < '0'.");
        }

        if (c != null && (c > getSizeC() - 1 || c < 0)) {
            throw new DimensionsOutOfBoundsException(
                "C '" + c + "' greater than sizeC '" + getSizeC() + "' or < '0'.");
        }

        if (t != null && (t > getSizeT() - 1 || t < 0)) {
            throw new DimensionsOutOfBoundsException(
                "T '" + t + "' greater than sizeT '" + getSizeT() + "' or < '0'.");
        }
    }

    /**
     * Checks the shape to read does not exceed the maximum plane size.
     **/
    public void checkReadSize(long[] shape) {
        long length = length(shape);
        long maxLength = maxPlaneWidth * maxPlaneHeight;
        if (length > maxLength) {
            throw new IllegalArgumentException(
                String.format("Requested shape %s > max plane size %d * %d", Arrays.toString(shape),
                    maxPlaneWidth, maxPlaneHeight));
        }
    }

    @Override
    public Long getPlaneSize() {
        return ((long) getRowSize()) * ((long) getSizeY());
    }

    @Override
    public Integer getRowSize() {
        return getSizeX() * getByteWidth();
    }

    @Override
    public Integer getColSize() {
        return getSizeY() * getByteWidth();
    }

    @Override
    public Long getStackSize() {
        return getPlaneSize() * ((long) getSizeZ());
    }

    @Override
    public Long getTimepointSize() {
        return getStackSize() * ((long) getSizeC());
    }

    @Override
    public Long getTotalSize() {
        return getTimepointSize() * ((long) getSizeT());
    }

    @Override
    public Long getHypercubeSize(List<Integer> offset, List<Integer> size, List<Integer> step)
        throws DimensionsOutOfBoundsException {
        throw new UnsupportedOperationException(
            "Zarr pixel buffer does not support Hypercube access");
    }

    @Override
    public Long getRowOffset(Integer y, Integer z, Integer c, Integer t)
        throws DimensionsOutOfBoundsException {
        throw new UnsupportedOperationException("Zarr pixel buffer does not provide row offsets");
    }

    @Override
    public Long getPlaneOffset(Integer z, Integer c, Integer t)
        throws DimensionsOutOfBoundsException {
        throw new UnsupportedOperationException("Zarr pixel buffer does not provide plane offsets");
    }

    @Override
    public Long getStackOffset(Integer c, Integer t) throws DimensionsOutOfBoundsException {
        throw new UnsupportedOperationException("Zarr pixel buffer does not provide stack offsets");
    }

    @Override
    public Long getTimepointOffset(Integer t) throws DimensionsOutOfBoundsException {
        throw new UnsupportedOperationException(
            "Zarr pixel buffer does not provide timepoint offsets");
    }

    @Override
    public PixelData getHypercube(List<Integer> offset, List<Integer> size, List<Integer> step)
        throws IOException, DimensionsOutOfBoundsException {
        throw new UnsupportedOperationException(
            "Zarr pixel buffer does not support Hypercube access");
    }

    @Override
    public byte[] getHypercubeDirect(List<Integer> offset, List<Integer> size, List<Integer> step,
        byte[] buffer) throws IOException, DimensionsOutOfBoundsException {
        throw new UnsupportedOperationException(
            "Zarr pixel buffer does not support Hypercube access");
    }

    @Override
    public byte[] getPlaneRegionDirect(Integer z, Integer c, Integer t, Integer count,
        Integer offset, byte[] buffer) throws IOException, DimensionsOutOfBoundsException {
        throw new UnsupportedOperationException(
            "Zarr pixel buffer does not support plane region access");
    }

    @Override
    public PixelData getTile(Integer z, Integer c, Integer t, Integer x, Integer y, Integer w,
        Integer h) throws IOException {
        // Check origin indices > 0
        checkBounds(x, y, z, c, t);
        // Check check bottom-right of tile in bounds
        checkBounds(x + w - 1, y + h - 1, z, c, t);
        // Check planar read size (sizeX and sizeY only), essential that this
        // happens before the similar check in read(). Otherwise we will
        // potentially allocate massive inner buffers in the tile cache
        // asynchronous entry builder that will never be used.
        checkReadSize(new long[] { w, h });

        List<List<Integer>> keys = new ArrayList<List<Integer>>();
        List<Integer> key = null;
        List<Integer> channels = Arrays.asList(new Integer[] { c });
        if (getSizeC() == 3) {
            // Guessing that we are in RGB mode
            channels = Arrays.asList(new Integer[] { 0, 1, 2 });
        }
        for (Integer channel : channels) {
            List<Integer> v = Arrays.asList(getResolutionLevel(), z, channel, t, x, y, w, h);
            keys.add(v);
            if (channel == c) {
                key = v;
            }
        }
        if (tileCache.getIfPresent(key) == null) {
            // We want to completely invalidate the cache if our key is not
            // present as relying on Caffeine to expire the previous triplicate
            // of channels can be unpredictable.
            tileCache.synchronous().invalidateAll();
        }
        return toPixelData(tileCache.getAll(keys).join().get(key));
    }

    @Override
    public byte[] getTileDirect(Integer z, Integer c, Integer t, Integer x, Integer y, Integer w,
        Integer h, byte[] buffer) throws IOException {
        try {
            // Check origin indices > 0
            checkBounds(x, y, z, c, t);
            // Check check bottom-right of tile in bounds
            checkBounds(x + w - 1, y + h - 1, z, c, t);

            long[] shape = new long[axesOrder.size()];
            long[] offset = new long[axesOrder.size()];
            if (axesOrder.containsKey(Axis.T)) {
                shape[axesOrder.get(Axis.T)] = 1;
                offset[axesOrder.get(Axis.T)] = t;
            }
            if (axesOrder.containsKey(Axis.C)) {
                shape[axesOrder.get(Axis.C)] = 1;
                offset[axesOrder.get(Axis.C)] = c;
            }
            if (axesOrder.containsKey(Axis.Z)) {
                shape[axesOrder.get(Axis.Z)] = 1;
                offset[axesOrder.get(Axis.Z)] = z;
            }
            shape[axesOrder.get(Axis.Y)] = h;
            shape[axesOrder.get(Axis.X)] = w;
            offset[axesOrder.get(Axis.Y)] = y;
            offset[axesOrder.get(Axis.X)] = x;

            read(buffer, shape, offset);
            return buffer;
        } catch (Exception e) {
            log.error("Error while retrieving pixel data", e);
            return null;
        }
    }

    @Override
    public PixelData getRegion(Integer size, Long offset) throws IOException {
        throw new UnsupportedOperationException("Zarr pixel buffer does not support region access");
    }

    @Override
    public byte[] getRegionDirect(Integer size, Long offset, byte[] buffer) throws IOException {
        throw new UnsupportedOperationException("Zarr pixel buffer does not support region access");
    }

    @Override
    public PixelData getRow(Integer y, Integer z, Integer c, Integer t)
        throws IOException, DimensionsOutOfBoundsException {
        return toPixelData(getRowDirect(y, z, c, t, new byte[getRowSize()]));
    }

    @Override
    public PixelData getCol(Integer x, Integer z, Integer c, Integer t)
        throws IOException, DimensionsOutOfBoundsException {
        return toPixelData(getColDirect(x, z, c, t, new byte[getColSize()]));
    }

    @Override
    public byte[] getRowDirect(Integer y, Integer z, Integer c, Integer t, byte[] buffer)
        throws IOException, DimensionsOutOfBoundsException {
        int x = 0;
        int w = getSizeX();
        int h = 1;
        return getTileDirect(z, c, t, x, y, w, h, buffer);
    }

    @Override
    public byte[] getColDirect(Integer x, Integer z, Integer c, Integer t, byte[] buffer)
        throws IOException, DimensionsOutOfBoundsException {
        int y = 0;
        int w = 1;
        int h = getSizeY();
        return getTileDirect(z, c, t, x, y, w, h, buffer);
    }

    @Override
    public PixelData getPlane(Integer z, Integer c, Integer t)
        throws IOException, DimensionsOutOfBoundsException {
        int planeSize = RomioPixelBuffer.safeLongToInteger(getPlaneSize());
        return toPixelData(getPlaneDirect(z, c, t, new byte[planeSize]));
    }

    @Override
    public PixelData getPlaneRegion(Integer x, Integer y, Integer width, Integer height, Integer z,
        Integer c, Integer t, Integer stride) throws IOException, DimensionsOutOfBoundsException {
        throw new UnsupportedOperationException(
            "Zarr pixel buffer does not support plane region access");
    }

    @Override
    public byte[] getPlaneDirect(Integer z, Integer c, Integer t, byte[] buffer)
        throws IOException, DimensionsOutOfBoundsException {
        int y = 0;
        int x = 0;
        int w = getSizeX();
        int h = getSizeY();
        return getTileDirect(z, c, t, x, y, w, h, buffer);
    }

    @Override
    public PixelData getStack(Integer c, Integer t)
        throws IOException, DimensionsOutOfBoundsException {
        int stackSize = RomioPixelBuffer.safeLongToInteger(getStackSize());
        byte[] buffer = new byte[stackSize];
        return toPixelData(getStackDirect(c, t, buffer));
    }

    @Override
    public byte[] getStackDirect(Integer c, Integer t, byte[] buffer)
        throws IOException, DimensionsOutOfBoundsException {
        int x = 0;
        int y = 0;
        int z = 0;
        int w = getSizeX();
        int h = getSizeY();

        // Check origin indices > 0
        checkBounds(x, y, z, c, t);
        // Check check bottom-right of tile in bounds
        checkBounds(x + w - 1, y + h - 1, z, c, t);

        long[] shape = new long[axesOrder.size()];
        long[] offset = new long[axesOrder.size()];
        if (axesOrder.containsKey(Axis.T)) {
            shape[axesOrder.get(Axis.T)] = 1;
            offset[axesOrder.get(Axis.T)] = t;
        }
        if (axesOrder.containsKey(Axis.C)) {
            shape[axesOrder.get(Axis.C)] = 1;
            offset[axesOrder.get(Axis.C)] = c;
        }
        if (axesOrder.containsKey(Axis.Z)) {
            shape[axesOrder.get(Axis.Z)] = getSizeZ();
            offset[axesOrder.get(Axis.Z)] = z;
        }
        shape[axesOrder.get(Axis.Y)] = h;
        shape[axesOrder.get(Axis.X)] = w;
        offset[axesOrder.get(Axis.Y)] = y;
        offset[axesOrder.get(Axis.X)] = x;

        read(buffer, shape, offset);
        return buffer;
    }

    @Override
    public PixelData getTimepoint(Integer t) throws IOException, DimensionsOutOfBoundsException {
        int timepointSize = RomioPixelBuffer.safeLongToInteger(getTimepointSize());
        byte[] buffer = new byte[timepointSize];
        return toPixelData(getTimepointDirect(t, buffer));
    }

    @Override
    public byte[] getTimepointDirect(Integer t, byte[] buffer)
        throws IOException, DimensionsOutOfBoundsException {
        int x = 0;
        int y = 0;
        int z = 0;
        int c = 0;
        int w = getSizeX();
        int h = getSizeY();

        // Check origin indices > 0
        checkBounds(x, y, z, c, t);
        // Check check bottom-right of tile in bounds
        checkBounds(x + w - 1, y + h - 1, z, c, t);

        long[] shape = new long[axesOrder.size()];
        long[] offset = new long[axesOrder.size()];
        if (axesOrder.containsKey(Axis.T)) {
            shape[axesOrder.get(Axis.T)] = 1;
            offset[axesOrder.get(Axis.T)] = t;
        }
        if (axesOrder.containsKey(Axis.C)) {
            shape[axesOrder.get(Axis.C)] = getSizeC();
            offset[axesOrder.get(Axis.C)] = c;
        }
        if (axesOrder.containsKey(Axis.Z)) {
            shape[axesOrder.get(Axis.Z)] = getSizeZ();
            offset[axesOrder.get(Axis.Z)] = z;
        }
        shape[axesOrder.get(Axis.Y)] = h;
        shape[axesOrder.get(Axis.X)] = w;
        offset[axesOrder.get(Axis.Y)] = y;
        offset[axesOrder.get(Axis.X)] = x;

        read(buffer, shape, offset);
        return buffer;
    }

    @Override
    public void setTile(byte[] buffer, Integer z, Integer c, Integer t, Integer x, Integer y,
        Integer w, Integer h) throws IOException, BufferOverflowException {
        throw new UnsupportedOperationException("Cannot write to Zarr");
    }

    @Override
    public void setRegion(Integer size, Long offset, byte[] buffer)
        throws IOException, BufferOverflowException {
        throw new UnsupportedOperationException("Cannot write to Zarr");
    }

    @Override
    public void setRegion(Integer size, Long offset, ByteBuffer buffer)
        throws IOException, BufferOverflowException {
        throw new UnsupportedOperationException("Cannot write to Zarr");
    }

    @Override
    public void setRow(ByteBuffer buffer, Integer y, Integer z, Integer c, Integer t)
        throws IOException, DimensionsOutOfBoundsException, BufferOverflowException {
        throw new UnsupportedOperationException("Cannot write to Zarr");
    }

    @Override
    public void setPlane(ByteBuffer buffer, Integer z, Integer c, Integer t)
        throws IOException, DimensionsOutOfBoundsException, BufferOverflowException {
        throw new UnsupportedOperationException("Cannot write to Zarr");
    }

    @Override
    public void setPlane(byte[] buffer, Integer z, Integer c, Integer t)
        throws IOException, DimensionsOutOfBoundsException, BufferOverflowException {
        throw new UnsupportedOperationException("Cannot write to Zarr");
    }

    @Override
    public void setStack(ByteBuffer buffer, Integer z, Integer c, Integer t)
        throws IOException, DimensionsOutOfBoundsException, BufferOverflowException {
        throw new UnsupportedOperationException("Cannot write to Zarr");
    }

    @Override
    public void setStack(byte[] buffer, Integer z, Integer c, Integer t)
        throws IOException, DimensionsOutOfBoundsException, BufferOverflowException {
        throw new UnsupportedOperationException("Cannot write to Zarr");
    }

    @Override
    public void setTimepoint(ByteBuffer buffer, Integer t)
        throws IOException, DimensionsOutOfBoundsException, BufferOverflowException {
        throw new UnsupportedOperationException("Cannot write to Zarr");
    }

    @Override
    public void setTimepoint(byte[] buffer, Integer t)
        throws IOException, DimensionsOutOfBoundsException, BufferOverflowException {
        throw new UnsupportedOperationException("Cannot write to Zarr");
    }

    @Override
    public byte[] calculateMessageDigest() throws IOException {
        throw new UnsupportedOperationException(
            "Zarr pixel buffer does not support message digest " + "calculation");
    }

    @Override
    public int getByteWidth() {
        return FormatTools.getBytesPerPixel(getPixelsType());
    }

    @Override
    public boolean isSigned() {
        return FormatTools.isSigned(getPixelsType());
    }

    @Override
    public boolean isFloat() {
        return FormatTools.isFloatingPoint(getPixelsType());
    }

    @Override
    public String getPath() {
        return root.toString();
    }

    @Override
    public long getId() {
        return 0;
    }

    @Override
    public int getSizeX() {
        long[] shape = (long[]) arrayMetadata.get("shape");
        return (int) shape[axesOrder.get(Axis.X)];
    }

    @Override
    public int getSizeY() {
        long[] shape = (long[]) arrayMetadata.get("shape");
        return (int) shape[axesOrder.get(Axis.Y)];
    }

    @Override
    public int getSizeZ() {
        if (axesOrder.containsKey(Axis.Z)) {
            // this is expected to be the Z size of the full resolution array
            return zIndexMap.size();
        }
        return 1;
    }

    /**
     * Returns the real Z size for the current resolution level.
     *
     * @return Z size of the current underlying Zarr array
     */
    private int getTrueSizeZ() {
        if (axesOrder.containsKey(Axis.Z)) {
            long[] shape = (long[]) arrayMetadata.get("shape");
            return (int) shape[axesOrder.get(Axis.Z)];
        }
        return 1;
    }

    @Override
    public int getSizeC() {
        if (axesOrder.containsKey(Axis.C)) {
            long[] shape = (long[]) arrayMetadata.get("shape");
            return (int) shape[axesOrder.get(Axis.C)];
        }
        return 1;
    }

    @Override
    public int getSizeT() {
        if (axesOrder.containsKey(Axis.T)) {
            long[] shape = (long[]) arrayMetadata.get("shape");
            return (int) shape[axesOrder.get(Axis.T)];
        }
        return 1;
    }

    @Override
    public int getResolutionLevels() {
        return getDatasets().size();
    }

    @Override
    public int getResolutionLevel() {
        // The pixel buffer API reverses the resolution level (0 is smallest)
        return Math.abs(resolutionLevel - (resolutionLevels - 1));
    }

    @Override
    public void setResolutionLevel(int resolutionLevel) {
        if (resolutionLevel >= resolutionLevels) {
            throw new IllegalArgumentException("Resolution level out of bounds!");
        }
        // The pixel buffer API reverses the resolution level (0 is smallest)
        this.resolutionLevel = Math.abs(resolutionLevel - (resolutionLevels - 1));
        if (this.resolutionLevel < 0) {
            throw new IllegalArgumentException("This Zarr file has no pixel data");
        }

        Map<Integer, Integer> tmpMap = new HashMap<>();
        try {
            array = zarrArrayCache.get(new ZarrPath(root,
                getDatasets().get(this.resolutionLevel).get("path"))).get();
            arrayMetadata = zarrMetadataCache.get(new ZarrPath(root,
                getDatasets().get(this.resolutionLevel).get("path"))).get();

            Map<String, Object> fullResolutionArrayMetadata = zarrMetadataCache
                .get(new ZarrPath(root, getDatasets().get(0).get("path"))).get();

            if (axesOrder.containsKey(Axis.Z)) {
                // map each Z index in the full resolution array
                // to a Z index in the subresolution array
                // if no Z downsampling, this is just an identity map
                long[] tmp = (long[]) fullResolutionArrayMetadata.get("shape");
                int fullResZ = (int) tmp[axesOrder.get(Axis.Z)];
                tmp = (long[]) arrayMetadata.get("shape");
                int arrayZ = (int) tmp[axesOrder.get(Axis.Z)];
                for (int z = 0; z < fullResZ; z++) {
                    tmpMap.put(z, Math.round(z * arrayZ / fullResZ));
                }
                zIndexMap = Map.copyOf(tmpMap);
            }
        } catch (Exception e) {
            // FIXME: Throw the right exception
            throw new RuntimeException(e);
        }

    }

    @Override
    public Dimension getTileSize() {
        try {
            int[] chunks = getChunks()[resolutionLevel];
            return new Dimension(chunks[axesOrder.get(Axis.X)], chunks[axesOrder.get(Axis.Y)]);
        } catch (Exception e) {
            // FIXME: Throw the right exception
            throw new RuntimeException(e);
        }
    }

    @Override
    public List<List<Integer>> getResolutionDescriptions() {
        try {
            int resolutionLevels = getResolutionLevels();
            List<List<Integer>> resolutionDescriptions = new ArrayList<List<Integer>>();
            int sizeX = pixels.getSizeX();
            int sizeY = pixels.getSizeY();
            for (int i = 0; i < resolutionLevels; i++) {
                double scale = Math.pow(2, i);
                resolutionDescriptions
                    .add(Arrays.asList((int) (sizeX / scale), (int) (sizeY / scale)));
            }
            return resolutionDescriptions;
        } catch (Exception e) {
            // FIXME: Throw the right exception
            throw new RuntimeException(e);
        }
    }

}
