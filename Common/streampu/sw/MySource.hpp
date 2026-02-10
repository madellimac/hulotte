#ifndef MYSOURCE_H
#define MYSOURCE_H

#include "streampu.hpp"

namespace spu
{
namespace module
{

class MySource  : public Stateful {

private:
    
    int frame_size;
    int data_width;

public:

MySource(int frame_size, int data_width);
    virtual ~MySource();

protected:

    virtual void generate(int *output, const int frame_id);

};
}
}

#endif // MYSOURCE_BINARY_H