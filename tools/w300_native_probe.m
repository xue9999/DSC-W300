// Native macOS USB capture and standard SCSI INQUIRY. No vendor/NVM writes.
#import <Foundation/Foundation.h>
#import <IOKit/IOKitLib.h>
#import <IOUSBHost/IOUSBHost.h>
#include <unistd.h>

static void require(BOOL ok, NSString *stage, NSError *error) {
    if (!ok) @throw [NSException exceptionWithName:@"ProbeError"
        reason:[NSString stringWithFormat:@"%@: %@", stage, error ?: @"validation failed"] userInfo:nil];
}

static NSMutableData *transfer(IOUSBHostPipe *pipe, NSData *out, NSUInteger length) {
    NSMutableData *data = out ? [out mutableCopy] : [NSMutableData dataWithLength:length];
    NSError *error = nil;
    NSUInteger actual = 0;
    BOOL ok = [pipe sendIORequestWithData:data bytesTransferred:&actual completionTimeout:2 error:&error];
    require(ok && actual == length, [NSString stringWithFormat:@"bulk (%lu/%lu)", actual, length], error);
    return data;
}

int main(int argc, char **argv) {
    @autoreleasepool {
        if (argc != 2) { fprintf(stderr, "Usage: w300_native_probe EXPECTED_USB_SERIAL\n"); return 2; }
        setbuf(stdout, NULL);
        NSString *expected = [NSString stringWithUTF8String:argv[1]];
        IOUSBHostDevice *device = nil;
        IOUSBHostInterface *interface = nil;
        io_service_t target = IO_OBJECT_NULL;
        BOOL configured = NO;
        int result = 1;
        @try {
            io_iterator_t iterator = IO_OBJECT_NULL;
            require(IOServiceGetMatchingServices(kIOMainPortDefault, IOServiceMatching("IOUSBHostDevice"), &iterator) == KERN_SUCCESS, @"enumeration", nil);
            io_service_t service;
            int matches = 0;
            while ((service = IOIteratorNext(iterator))) {
                CFMutableDictionaryRef raw = NULL;
                if (IORegistryEntryCreateCFProperties(service, &raw, kCFAllocatorDefault, 0) == KERN_SUCCESS) {
                    NSDictionary *props = CFBridgingRelease(raw);
                    if ([props[@"idVendor"] intValue] == 0x054c && [props[@"idProduct"] intValue] == 0x0341 &&
                        [props[@"USB Product Name"] isEqual:@"DSC-W300"] && [props[@"USB Serial Number"] isEqual:expected]) {
                        matches++;
                        if (target) IOObjectRelease(target);
                        target = service;
                        IOObjectRetain(target);
                    }
                }
                IOObjectRelease(service);
            }
            IOObjectRelease(iterator);
            require(matches == 1, @"unique W300 identity", nil);
            NSError *error = nil;
            device = [[IOUSBHostDevice alloc] initWithIOService:target options:IOUSBHostObjectInitOptionsDeviceCapture
                queue:nil error:&error interestHandler:nil];
            require(device != nil, @"native capture", error);
            puts("Native device capture succeeded");
            require([device configureWithValue:1 matchInterfaces:NO error:&error], @"configure without kernel matching", error);
            configured = YES;
            puts("Configured without kernel matching; opening interface");
            for (int attempt=0; attempt<20 && !interface; attempt++) {
                iterator = IO_OBJECT_NULL;
                if (IORegistryEntryCreateIterator(device.ioService, kIOServicePlane, kIORegistryIterateRecursively, &iterator) == KERN_SUCCESS) {
                    while ((service = IOIteratorNext(iterator))) {
                        if (IOObjectConformsTo(service, "IOUSBHostInterface")) {
                            interface = [[IOUSBHostInterface alloc] initWithIOService:service options:IOUSBHostObjectInitOptionsNone
                                queue:nil error:&error interestHandler:nil];
                        }
                        IOObjectRelease(service);
                        if (interface) break;
                    }
                    IOObjectRelease(iterator);
                }
                if (!interface) usleep(100000);
            }
            require(interface != nil, @"native interface open", error);
            const IOUSBInterfaceDescriptor *desc = interface.interfaceDescriptor;
            require(desc && desc->bInterfaceNumber == 0 && desc->bInterfaceClass == 8 &&
                desc->bInterfaceSubClass == 5 && desc->bInterfaceProtocol == 0x50, @"MSC interface", nil);
            IOUSBHostPipe *input = [interface copyPipeWithAddress:0x81 error:&error];
            require(input != nil, @"input pipe", error);
            IOUSBHostPipe *output = [interface copyPipeWithAddress:0x02 error:&error];
            require(output != nil, @"output pipe", error);
            puts("Native bulk pipes opened");
            unsigned char cbw[31] = {'U','S','B','C','W','3','0','0',36,0,0,0,0x80,0,12,0x12,0,0,0,36,0};
            transfer(output, [NSData dataWithBytes:cbw length:31], 31);
            NSData *reply = transfer(input, nil, 36);
            NSData *status = transfer(input, nil, 13);
            const unsigned char *csw = status.bytes;
            require(!memcmp(csw, "USBSW300", 8) && !csw[8] && !csw[9] && !csw[10] && !csw[11] && !csw[12], @"INQUIRY status", nil);
            const unsigned char *data = reply.bytes;
            printf("INQUIRY hex:");
            for (int i=0; i<36; i++) printf("%02x", data[i]);
            printf("\nVendor: %.8s\nModel: %.16s\nRevision: %.4s\n", data+8, data+16, data+32);
            puts("Camera configuration/NVM writes: none");
            result = 0;
        } @catch (NSException *exception) {
            fprintf(stderr, "%s\n", exception.reason.UTF8String);
            fprintf(stderr, "%s\n", exception.callStackSymbols.description.UTF8String);
        } @finally {
            [interface destroy];
            if (configured) {
                NSError *error = nil;
                BOOL ok = [device configureWithValue:1 matchInterfaces:YES error:&error];
                printf("Restore kernel matching: %s\n", ok ? "OK" : error.description.UTF8String);
                if (!ok) result = 1;
            }
            [device destroy];
            if (target) IOObjectRelease(target);
        }
        return result;
    }
}
