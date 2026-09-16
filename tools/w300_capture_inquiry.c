/* Bounded macOS USB capture + standard SCSI INQUIRY for observed DSC-W300.
 * No vendor/service commands, disk writes, NVM operations or firmware upload.
 * The only bulk OUT payload is a BOT wrapper for INQUIRY (read, opcode 0x12).
 * Requires serial argument; accepts only 054c:0341 and observed interface shape.
 * Kernel driver is reattached on exit. Run when no camera volume is mounted.
 */
#include <libusb.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>

static int bulk(libusb_device_handle *h, unsigned char ep,
                unsigned char *data, int size) {
    int actual = 0;
    int rc = libusb_bulk_transfer(h, ep, data, size, &actual, 1500);
    if (rc || actual != size) {
        fprintf(stderr, "bulk ep=%02x rc=%s actual=%d expected=%d\n",
                ep, libusb_error_name(rc), actual, size);
        return -1;
    }
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "Usage: w300_capture_inquiry EXPECTED_USB_SERIAL\n");
        return 2;
    }
    libusb_context *ctx = NULL;
    libusb_device **list = NULL, *target = NULL;
    libusb_device_handle *handle = NULL;
    struct libusb_config_descriptor *cfg = NULL;
    int rc, result = 1, detached = 0, claimed = 0, matches = 0;
    rc = libusb_init(&ctx);
    if (rc) { fprintf(stderr, "init: %s\n", libusb_error_name(rc)); return 1; }
    ssize_t count = libusb_get_device_list(ctx, &list);
    if (count < 0) goto cleanup;
    for (ssize_t i = 0; i < count; i++) {
        struct libusb_device_descriptor d;
        if (!libusb_get_device_descriptor(list[i], &d) && d.idVendor == 0x054c && d.idProduct == 0x0341) {
            target = list[i]; matches++;
        }
    }
    if (matches != 1) { fprintf(stderr, "Expected exactly one 054c:0341, found %d\n", matches); goto cleanup; }
    rc = libusb_open(target, &handle);
    if (rc) { fprintf(stderr, "open: %s\n", libusb_error_name(rc)); goto cleanup; }
    struct libusb_device_descriptor d;
    if (libusb_get_device_descriptor(target, &d)) goto cleanup;
    unsigned char serial[256] = {0}, product[256] = {0};
    if (libusb_get_string_descriptor_ascii(handle, d.iSerialNumber, serial, sizeof(serial)-1) < 0 ||
        libusb_get_string_descriptor_ascii(handle, d.iProduct, product, sizeof(product)-1) < 0 ||
        strcmp((char *)serial, argv[1]) || strcmp((char *)product, "DSC-W300")) {
        fprintf(stderr, "USB identity mismatch\n"); goto cleanup;
    }
    rc = libusb_get_active_config_descriptor(target, &cfg);
    if (rc || cfg->bNumInterfaces != 1 || cfg->interface[0].num_altsetting != 1) {
        fprintf(stderr, "Unexpected USB configuration\n"); goto cleanup;
    }
    const struct libusb_interface_descriptor *iface = &cfg->interface[0].altsetting[0];
    if (iface->bInterfaceNumber != 0 || iface->bInterfaceClass != 8 ||
        iface->bInterfaceSubClass != 5 || iface->bInterfaceProtocol != 0x50 || iface->bNumEndpoints != 2) {
        fprintf(stderr, "Unexpected USB interface\n"); goto cleanup;
    }
    int endpoints = 0;
    for (int i=0; i<2; i++) {
        const struct libusb_endpoint_descriptor *ep = &iface->endpoint[i];
        if (ep->bmAttributes != 2 || ep->wMaxPacketSize != 512) goto cleanup;
        if (ep->bEndpointAddress == 0x81) endpoints |= 1;
        if (ep->bEndpointAddress == 0x02) endpoints |= 2;
    }
    if (endpoints != 3) goto cleanup;
    printf("Identity and interface verified: DSC-W300 054c:0341\n"); fflush(stdout);
    rc = libusb_detach_kernel_driver(handle, 0);
    printf("detach: %s\n", libusb_error_name(rc)); fflush(stdout);
    if (rc) goto cleanup;
    detached = 1;
    rc = libusb_claim_interface(handle, 0);
    printf("claim: %s\n", libusb_error_name(rc)); fflush(stdout);
    if (rc) goto cleanup;
    claimed = 1;

    /* CBW: tag W300, 36-byte IN transfer, LUN 0, 12-byte SFF8070 command. */
    unsigned char cbw[31] = {'U','S','B','C','W','3','0','0',36,0,0,0,0x80,0,12,0x12,0,0,0,36,0};
    unsigned char data[36] = {0}, csw[13] = {0};
    if (bulk(handle, 0x02, cbw, sizeof(cbw)) || bulk(handle, 0x81, data, sizeof(data)) ||
        bulk(handle, 0x81, csw, sizeof(csw))) goto cleanup;
    if (memcmp(csw, "USBSW300", 8) || csw[8] || csw[9] || csw[10] || csw[11] || csw[12]) {
        fprintf(stderr, "INQUIRY status rejected\n"); goto cleanup;
    }
    printf("INQUIRY hex:");
    for (int i=0; i<36; i++) printf("%02x", data[i]);
    printf("\nVendor: %.8s\nModel: %.16s\nRevision: %.4s\n", data+8, data+16, data+32);
    printf("Camera configuration/NVM writes: none\n");
    result = 0;
cleanup:
    if (claimed) {
        rc = libusb_release_interface(handle, 0);
        printf("release: %s\n", libusb_error_name(rc));
        if (rc) result = 1;
    }
    if (detached) {
        rc = libusb_attach_kernel_driver(handle, 0);
        printf("reattach: %s\n", libusb_error_name(rc));
        if (rc) result = 1;
    }
    if (cfg) libusb_free_config_descriptor(cfg);
    if (handle) libusb_close(handle);
    if (list) libusb_free_device_list(list, 1);
    libusb_exit(ctx);
    return result;
}
